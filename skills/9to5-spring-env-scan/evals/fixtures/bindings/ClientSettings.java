@ConfigurationProperties(prefix = "client")
class ClientSettings {
    private int connectTimeout;
    private Credentials credentials;
    static String INTERNAL_CONSTANT;
    public int getConnectTimeout() { int local = 0; return connectTimeout; }
    static class Credentials {
        private String userName;
    }
}
