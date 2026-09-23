# Confluence storage format

Confluence stores page bodies as an XHTML dialect called **storage format**: ordinary
HTML elements plus `ac:` macros for the features the editor exposes. The REST API accepts
it in `body.storage.value`, and `scripts/confluence.py` sends it by default
(`--body-file`). `--format wiki` sends wiki markup instead.

Nothing validates the body. Invalid markup saves successfully and renders wrong, so
always re-read the page after a write.

## Plain content

```xml
<h1>Heading</h1>
<h2>Subheading</h2>
<p>Text with <strong>bold</strong>, <em>italic</em> and <code>inline code</code>.</p>
<ul><li>item</li><li>item</li></ul>
<ol><li>first</li><li>second</li></ol>
<p><a href="https://example.invalid/report">external link</a></p>
<hr/>
```

Escape `&` as `&amp;`, `<` as `&lt;`, `>` as `&gt;` in text. Never paste markdown
syntax — `**bold**` and `| a | b |` render literally.

## Code block

```xml
<ac:structured-macro ac:name="code" ac:schema-version="1">
  <ac:parameter ac:name="language">sql</ac:parameter>
  <ac:plain-text-body><![CDATA[
SELECT 1 FROM dual;
  ]]></ac:plain-text-body>
</ac:structured-macro>
```

Inside `CDATA` nothing needs escaping, but a literal `]]>` must be split as `]]]]><![CDATA[>`.

## Panels and status

```xml
<ac:structured-macro ac:name="info" ac:schema-version="1">
  <ac:rich-text-body><p>Context worth knowing.</p></ac:rich-text-body>
</ac:structured-macro>
```

`ac:name` accepts `info`, `note`, `warning`, `tip`.

```xml
<ac:structured-macro ac:name="status" ac:schema-version="1">
  <ac:parameter ac:name="colour">Green</ac:parameter>
  <ac:parameter ac:name="title">DONE</ac:parameter>
</ac:structured-macro>
```

## Tables

```xml
<table>
  <tbody>
    <tr><th>Service</th><th>Tag</th></tr>
    <tr><td>notification-service</td><td>v1.8.3</td></tr>
  </tbody>
</table>
```

Row and cell highlighting needs **both** attributes with the same value, because
Confluence renders from the class:

```xml
<tr><td class="highlight-purple" data-highlight-colour="purple">needs release</td></tr>
```

`purple`, `grey`, `red`, `yellow`, `green`, `blue` are the named colours; a hex value such
as `#998dd9` also works. The release skills use this convention — do not invent a variant.

## Links, images, macros

```xml
<!-- link to another page in the same space -->
<ac:link>
  <ri:page ri:content-title="Release PROD"/>
  <ac:plain-text-link-body><![CDATA[Release PROD]]></ac:plain-text-link-body>
</ac:link>

<!-- attached image; upload it first with `attach` -->
<ac:image><ri:attachment ri:filename="diagram.png"/></ac:image>

<!-- table of contents -->
<ac:structured-macro ac:name="toc" ac:schema-version="1"/>

<!-- collapsible section -->
<ac:structured-macro ac:name="expand" ac:schema-version="1">
  <ac:parameter ac:name="title">Details</ac:parameter>
  <ac:rich-text-body><p>Hidden until expanded.</p></ac:rich-text-body>
</ac:structured-macro>
```

An `<ac:image>` pointing at a file that was never attached renders as a broken image and
saves without complaint. Attach first, then reference.

## Wiki markup alternative

`--format wiki` skips the XHTML and sends Confluence wiki markup, which is quicker for
simple pages:

```
h1. Heading
*bold* _italic_ {{inline code}}
* item
# item

||Service||Tag||
|notification-service|v1.8.3|

{code:language=sql}
SELECT 1 FROM dual;
{code}

{info}Context worth knowing.{info}
```

Wiki markup has no equivalent for every macro, and tables lose per-cell attributes. Use
storage format for anything structured — release tables, specification pages, or content
another skill will later parse.
