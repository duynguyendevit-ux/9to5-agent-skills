"""Offline contract tests for the value-free Java/Spring inventory."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ.get('SKILLS_ROOT', Path(__file__).resolve().parents[1] / 'skills'))
SCRIPT = ROOT / '9to5-spring-env-scan/scripts/scan_env.py'
spec = importlib.util.spec_from_file_location('spring_env_scan', SCRIPT)
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


class SpringEnvScanTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def run_scan(self, *args, expected=0):
        result = subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root),
                                 '--format', 'json', *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stderr + result.stdout)
        self.assertEqual(result.stderr, '')
        return json.loads(result.stdout)

    def named(self, report, section):
        return {item['name']: item for item in report[section]}

    def test_yaml_aliases_defaults_and_value_consumer(self):
        self.write('src/main/resources/application.yaml', '''app:
  timeout: ${REQUEST_TIMEOUT:5000}
  alias: ${app.timeout}
  password: ${DB_PASSWORD:FAKE_SECRET_SENTINEL}
''')
        self.write('src/main/java/Worker.java', '''class Worker {
 @Value("${app.alias}") String alias;
 @Value("${DIRECT_ENV:FAKE_JAVA_SECRET}") String direct;
}''')
        report = self.run_scan()
        variables = self.named(report, 'variables')
        self.assertEqual(set(variables), {'REQUEST_TIMEOUT', 'DB_PASSWORD', 'DIRECT_ENV'})
        prop = self.named(report, 'properties')['app.alias']
        self.assertEqual(prop['variables'], ['REQUEST_TIMEOUT'])
        self.assertIn('@Value', {e['kind'] for e in prop['evidence']})
        self.assertEqual(variables['DB_PASSWORD']['evidence'][0]['default'], 'has_default')
        for text in (json.dumps(report), scanner.markdown(report)):
            self.assertNotIn('FAKE_SECRET_SENTINEL', text)
            self.assertNotIn('FAKE_JAVA_SECRET', text)
            self.assertNotIn('5000', text)

    def test_nested_fallbacks_and_no_runtime_required_claim(self):
        self.write('application.yml', 'url: ${PRIMARY_URL:${BACKUP_URL:https://example.invalid:443/a}}\nflag: ${FEATURE_FLAG}\n')
        report = self.run_scan()
        variables = self.named(report, 'variables')
        self.assertEqual(set(variables), {'PRIMARY_URL', 'BACKUP_URL', 'FEATURE_FLAG'})
        self.assertEqual(variables['BACKUP_URL']['evidence'][0]['default'], 'has_default')
        self.assertEqual(variables['FEATURE_FLAG']['evidence'][0]['default'], 'no_default')
        self.assertNotIn('required', json.dumps(report))

    def test_profiles_anchors_sequences_and_multimodule(self):
        self.write('module-a/application-dev.yaml', '''base: &defaults
  host: ${SHARED_HOST}
app:
  <<: *defaults
  servers:
    - ${FIRST_SERVER}
---
app:
  host: ${PROD_HOST}
''')
        self.write('module-b/application.properties', 'worker.enabled=${WORKER_ENABLED:true}\n')
        report = self.run_scan()
        self.assertEqual(report['coverage']['profiles'], 'inventory_only')
        self.assertEqual(len(report['coverage']['files']), 2)
        props = self.named(report, 'properties')
        self.assertEqual(props['app.host']['variables'], ['PROD_HOST', 'SHARED_HOST'])
        self.assertEqual({e['document'] for e in props['app.host']['evidence']}, {1, 2})
        self.assertEqual(props['app.servers[0]']['variables'], ['FIRST_SERVER'])
        self.assertNotIn('APP_SERVERS[0]', self.named(report, 'inferred_variables'))

    def test_properties_escapes_continuations_and_document_separator(self):
        self.write('application.properties', '# ignored=${COMMENT_ONLY}\napp.connect-timeout = ${TIMEOUT:\\\n  1000}\napp.h\\u006fst:${HOST}\nescaped\\:key=${ODD}\n#---\napp.host=${SECOND_HOST}\n')
        report = self.run_scan(expected=1)
        props = self.named(report, 'properties')
        self.assertEqual(props['app.host']['variables'], ['HOST', 'SECOND_HOST'])
        self.assertEqual(self.named(report, 'variables')['TIMEOUT']['evidence'][0]['line'], 2)
        self.assertNotIn('COMMENT_ONLY', self.named(report, 'variables'))
        self.assertIn('unsupported_property_key', {w['code'] for w in report['warnings']})

    def test_java_comments_escaped_strings_dynamic_lookups_and_system_properties(self):
        self.write('Config.java', r'''class Config {
 // System.getenv("COMMENT_ENV");
 /* @Value("${BLOCK_ENV}") */
 String host = System.getenv("REAL\u005fHOST");
 String dynamic = System.getenv(prefix + "_HOST");
 String suffix = System.getenv("BAD" + suffix);
 String jvm = System.getProperty("jvm.custom");
 String spring = env.getProperty("app.enabled", "VALUE_WITHHELD");
 String required = env.getRequiredProperty("app.timeout");
 boolean present = env.containsProperty("app.ready");
 String example = "System.getenv(\"STRING_ENV\")";
}''')
        report = self.run_scan(expected=1)
        self.assertEqual(set(self.named(report, 'variables')), {'REAL_HOST'})
        self.assertNotIn('JVM_CUSTOM', self.named(report, 'inferred_variables'))
        self.assertIn('APP_ENABLED', self.named(report, 'inferred_variables'))
        self.assertEqual(len([w for w in report['warnings'] if w['code'] == 'dynamic_lookup_argument']), 2)
        self.assertNotIn('VALUE_WITHHELD', json.dumps(report))

    def test_configuration_class_fields_nested_types_and_exact_lines(self):
        self.write('application.yml', 'worker:\n  batch-size: ${BATCH_SIZE:10}\n  retry:\n    max-attempts: ${MAX_ATTEMPTS:3}\n')
        self.write('WorkerProperties.java', '''@ConfigurationProperties(prefix = "worker")
public class WorkerProperties {
 @NotNull
 private int batchSize;
 private Retry retry = new Retry();
 static String NOT_CONFIG = "IGNORED";
 public int getBatchSize() { int local = 1; return batchSize; }
 static class Retry {
   private int maxAttempts;
 }
}''')
        report = self.run_scan()
        props = self.named(report, 'properties')
        self.assertEqual(props['worker.batch-size']['variables'], ['BATCH_SIZE'])
        bindings = [e for e in props['worker.batch-size']['evidence'] if e['kind'] == 'config_binding']
        self.assertEqual([e['line'] for e in bindings], [4])
        self.assertEqual(props['worker.retry.max-attempts']['variables'], ['MAX_ATTEMPTS'])
        self.assertNotIn('worker.local', props)
        self.assertNotIn('worker.not-config', props)

    def test_records_qualified_annotation_and_empty_prefix(self):
        self.write('App.java', '''@org.springframework.boot.context.properties.ConfigurationProperties("my.service")
record Settings(@NotNull String apiURL, java.time.Duration connectTimeout) {}
@ConfigurationProperties(prefix = "")
record RootConfig(boolean enabled) {}
''')
        report = self.run_scan()
        props = self.named(report, 'properties')
        self.assertIn('my.service.api-url', props)
        self.assertIn('my.service.connect-timeout', props)
        self.assertIn('enabled', props)
        inferred = self.named(report, 'inferred_variables')
        self.assertIn('MY_SERVICE_CONNECTTIMEOUT', inferred)
        self.assertNotIn('MY_SERVICE_CONNECT_TIMEOUT', inferred)

    def test_annotation_default_prefix_and_initialized_multifields(self):
        self.write('Settings.java', '''@ConfigurationProperties
record Settings(@NotNull String host) {}
@ConfigurationProperties("other")
class Other { String mode = "static"; int a = 1, b = 2; }
''')
        report = self.run_scan(expected=1)
        props = self.named(report, 'properties')
        self.assertIn('host', props)
        self.assertIn('other.mode', props)
        self.assertNotIn('other.a', props)
        self.assertIn('multiple_config_field_declaration', {w['code'] for w in report['warnings']})

    def test_factory_method_resolves_local_return_class(self):
        self.write('Config.java', '''class Beans {
 @ConfigurationProperties(value="client")
 @Bean
 public ClientSettings client() { return new ClientSettings(); }
}
class ClientSettings { private String endpoint; }
''')
        report = self.run_scan()
        self.assertIn('client.endpoint', self.named(report, 'properties'))

    def test_collection_inheritance_and_multiple_fields_warn(self):
        self.write('Props.java', '''@ConfigurationProperties("app")
class Props extends Base {
 List<String> hosts;
 int first, second;
 private External config;
}''')
        report = self.run_scan(expected=1)
        codes = {w['code'] for w in report['warnings']}
        self.assertTrue({'collection_config_not_expanded', 'inherited_config_fields_not_scanned',
                         'multiple_config_field_declaration', 'external_or_unsupported_config_type'} <= codes)
        self.assertNotIn('APP_HOSTS', self.named(report, 'inferred_variables'))

    def test_ambiguous_factory_type_warns(self):
        self.write('Beans.java', '@ConfigurationProperties("client")\nClientSettings client() { return null; }\n')
        self.write('one/ClientSettings.java', 'class ClientSettings { String host; }')
        self.write('two/ClientSettings.java', 'class ClientSettings { String host; }')
        report = self.run_scan(expected=1)
        self.assertIn('unresolved_factory_config_type', {w['code'] for w in report['warnings']})

    def test_tests_generated_dirs_symlinks_and_exclude(self):
        self.write('src/main/application.yaml', 'key: ${MAIN_ENV}\n')
        self.write('src/test/application.yaml', 'key: ${TEST_ENV}\n')
        self.write('build/application.yaml', 'key: ${BUILD_ENV}\n')
        self.write('target/application.yaml', 'key: ${TARGET_ENV}\n')
        outside = self.write('other/settings.yaml', 'key: ${LINK_ENV}\n')
        (self.root / 'application-link.yaml').symlink_to(outside)
        report = self.run_scan()
        self.assertEqual(set(self.named(report, 'variables')), {'MAIN_ENV'})
        report = self.run_scan('--include-tests')
        self.assertEqual(set(self.named(report, 'variables')), {'MAIN_ENV', 'TEST_ENV'})
        report = self.run_scan('--exclude', 'src/main/**', '--include-tests')
        self.assertEqual(set(self.named(report, 'variables')), {'TEST_ENV'})

    def test_custom_config_and_import_warning(self):
        self.write('application.yml', 'spring.config.import: optional:classpath:custom.yaml\n')
        self.write('custom.yaml', 'custom.key: ${CUSTOM_ENV}\n')
        report = self.run_scan('--config', 'custom.yaml', expected=1)
        self.assertIn('CUSTOM_ENV', self.named(report, 'variables'))
        self.assertIn('config_import_not_resolved', {w['code'] for w in report['warnings']})

    def test_invalid_yaml_dynamic_placeholders_and_secret_free_errors(self):
        self.write('application.yml', 'password: [FAKE_YAML_SECRET\n')
        self.write('application-dev.yml', 'key: ${${DYNAMIC_KEY}:FAKE_DEFAULT_SECRET}\n')
        report = self.run_scan(expected=1)
        self.assertNotIn('FAKE_YAML_SECRET', json.dumps(report))
        self.assertNotIn('FAKE_DEFAULT_SECRET', scanner.markdown(report))
        codes = {w['code'] for w in report['warnings']}
        self.assertTrue({'invalid_yaml', 'dynamic_or_malformed_placeholder'} <= codes)

    def test_recursive_alias_and_property_cycles_terminate(self):
        self.write('application.yml', 'app: &self\n  nested: *self\nx: ${y}\ny: ${x:${CYCLE_FALLBACK}}\n')
        report = self.run_scan(expected=1)
        self.assertIn('recursive_yaml_alias', {w['code'] for w in report['warnings']})
        self.assertEqual(self.named(report, 'properties')['x']['variables'], ['CYCLE_FALLBACK'])

    def test_names_only_output_is_not_an_empty_dotenv_override(self):
        self.write('application.yml', 'app.host: ${HOST:FAKE_DEFAULT_SECRET}\n')
        run = subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root),
                              '--format', 'env'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0)
        self.assertIn('\nHOST\n', run.stdout)
        self.assertNotIn('HOST=', run.stdout)
        self.assertNotIn('FAKE_DEFAULT_SECRET', run.stdout)
        self.assertNotIn('APP_HOST', run.stdout)

    def test_bad_root_and_custom_config_escape_return_two(self):
        for args in [('--root', str(self.root / 'missing')),
                     ('--root', str(self.root), '--config', '../outside.yaml')]:
            run = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(run.stdout, '')

    def test_empty_scan_and_unreadable_utf8_are_partial(self):
        report = self.run_scan(expected=1)
        self.assertEqual(report['warnings'][0]['code'], 'no_supported_files')
        (self.root / 'Bad.java').write_bytes(b'\xff')
        report = self.run_scan(expected=1)
        self.assertIn('unreadable_source', {w['code'] for w in report['warnings']})

    def test_markdown_escapes_paths_and_keeps_evidence(self):
        self.write('module|name/application.yaml', 'host: ${HOST}\n')
        report = self.run_scan()
        self.assertIn('module\\|name/application.yaml:1', scanner.markdown(report))

    def test_java_octal_is_not_properties_octal(self):
        self.assertEqual(scanner.decode_literal(r'ENV\137NAME', java=True), 'ENV_NAME')
        self.assertEqual(scanner.decode_literal(r'ENV\137NAME'), 'ENV137NAME')

    def test_postfix_array_and_qualified_type_warn_only_for_collection(self):
        self.write('Props.java', '''@ConfigurationProperties("app")
class Props { java.time.Duration timeout; String hosts[]; }
''')
        report = self.run_scan(expected=1)
        self.assertEqual({w['code'] for w in report['warnings']}, {'collection_config_not_expanded'})
        self.assertIn('APP_TIMEOUT', self.named(report, 'inferred_variables'))
        self.assertNotIn('APP_HOSTS', self.named(report, 'inferred_variables'))

    def test_custom_configs_respect_exclude_and_symlink_parent_is_rejected(self):
        self.write('application.yaml', 'key: ${MAIN_ENV}\n')
        self.write('custom/settings.yaml', 'key: ${CUSTOM_ENV}\n')
        report = self.run_scan('--config', 'custom/settings.yaml', '--exclude', 'custom/**')
        self.assertEqual(set(self.named(report, 'variables')), {'MAIN_ENV'})
        (self.root / 'link').symlink_to(self.root / 'custom', target_is_directory=True)
        run = subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root),
                              '--config', 'link/settings.yaml'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)

    def test_duplicate_keys_warn_and_list_import_is_not_silently_resolved(self):
        self.write('application.yml', 'key: ${FIRST}\nkey: ${SECOND}\nspring:\n  config:\n    import:\n      - optional:classpath:other.yaml\n')
        report = self.run_scan(expected=1)
        self.assertTrue({'duplicate_yaml_key', 'config_import_not_resolved'} <= {w['code'] for w in report['warnings']})
        self.assertEqual(self.named(report, 'properties')['key']['variables'], ['FIRST', 'SECOND'])

    def test_long_property_alias_chain_does_not_recurse_in_python(self):
        self.write('application.properties', '\n'.join(f'key{i}=${{key{i+1}}}' for i in range(1100)) + '\nkey1100=${TERMINAL_ENV}\n')
        report = self.run_scan()
        self.assertEqual(self.named(report, 'properties')['key0']['variables'], ['TERMINAL_ENV'])

    def test_factory_named_annotation_and_default_prefix_options(self):
        self.write('Bean.java', '''class Beans {
 @ConfigurationProperties(prefix="client")
 @Bean(name="clientSettings")
 public ClientSettings client() { return new ClientSettings(); }
}
class ClientSettings { String host; }
@ConfigurationProperties(ignoreUnknownFields=false)
record RootSettings(String endpoint) {}
''')
        report = self.run_scan()
        self.assertTrue({'client.host', 'endpoint'} <= set(self.named(report, 'properties')))

    def test_comparison_in_field_initializer_does_not_swallow_following_field(self):
        self.write('Settings.java', '''@ConfigurationProperties("app")
class Settings { int batchSize = LOW < HIGH ? 1 : 2; String host; }
''')
        report = self.run_scan()
        self.assertTrue({'app.batch-size', 'app.host'} <= set(self.named(report, 'properties')))

    def test_uppercase_environment_style_lookup_is_not_a_jvm_env_claim(self):
        self.write('Env.java', '''class Env {
 String host = environment.getProperty("DB_HOST");
 String password = environment.getRequiredProperty("DB_PASSWORD");
 String jvm = System.getProperty("JVM_ONLY");
}''')
        report = self.run_scan()
        variables = self.named(report, 'variables')
        self.assertEqual(set(variables), {'DB_HOST', 'DB_PASSWORD'})
        self.assertEqual(variables['DB_HOST']['evidence'][0]['confidence'], 'heuristic_receiver')
        self.assertNotIn('JVM_ONLY', variables)


if __name__ == '__main__':
    unittest.main()
