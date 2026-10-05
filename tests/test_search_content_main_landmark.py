"""Page text comes from the element the page marks as its main content.

``fetch_webpage_content`` used to take the first three elements whose class
matched ``content|main|body|article|post|entry|text``, in document order. On
English Wikipedia (Vector 2022 skin) those three are all containers of the
site's "Main menu" in the header, so every desktop article came back as the
navigation menu three times over and no article text: 627 characters, just
above the 600-character threshold that would have triggered the body-text
fallback. Every cached ``en.wikipedia.org/wiki/...`` fetch in
``data/cache/content`` from 2026-07-31 to 2026-10-05 had exactly that content.

``WIKIPEDIA_VECTOR_2022`` is a reduced copy of the live markup: element names,
ids and classes follow a saved Vector 2022 page (mozilla/readability test page
``wikipedia-4``), with the main-menu dropdown populated as the live site
serves it. On the pre-fix code it reproduces the recorded 627-character
extract exactly (``RECORDED_MENU_ONLY_EXTRACT``), which is what makes it a
fixture for the real failure and not just for the mechanism.
"""

import pytest

pytest.importorskip("bs4")

from services.search import content as service_content


# What the pre-fix extractor returned for every desktop English Wikipedia
# article (copied from data/cache/content, url .../wiki/Edible_mushroom).
RECORDED_MENU_ONLY_EXTRACT = (
    "Main menu Main menu move to sidebar hide Navigation Main page Contents "
    "Current events Random article About Wikipedia Contact us Contribute Help "
    "Learn to edit Community portal Recent changes Upload file Special pages "
    "Main menu move to sidebar hide Navigation Main page Contents Current "
    "events Random article About Wikipedia Contact us Contribute Help Learn "
    "to edit Community portal Recent changes Upload file Special pages Main "
    "menu move to sidebar hide Navigation Main page Contents Current events "
    "Random article About Wikipedia Contact us Contribute Help Learn to edit "
    "Community portal Recent changes Upload file Special pages"
)

_MAIN_MENU = """
<div id="vector-main-menu" class="vector-main-menu vector-pinnable-element">
  <div class="vector-pinnable-header vector-main-menu-pinnable-header vector-pinnable-header-unpinned">
    <div class="vector-pinnable-header-label">Main menu</div>
    <button class="vector-pinnable-header-toggle-button vector-pinnable-header-pin-button">move to sidebar</button>
    <button class="vector-pinnable-header-toggle-button vector-pinnable-header-unpin-button">hide</button>
  </div>
  <div id="p-navigation" class="vector-menu mw-portlet mw-portlet-navigation">
    <div class="vector-menu-heading">Navigation</div>
    <div class="vector-menu-content"><ul class="vector-menu-content-list">
      <li><a href="/wiki/Main_Page"><span>Main page</span></a></li>
      <li><a href="/wiki/Wikipedia:Contents"><span>Contents</span></a></li>
      <li><a href="/wiki/Portal:Current_events"><span>Current events</span></a></li>
      <li><a href="/wiki/Special:Random"><span>Random article</span></a></li>
      <li><a href="/wiki/Wikipedia:About"><span>About Wikipedia</span></a></li>
      <li><a href="//en.wikipedia.org/wiki/Wikipedia:Contact_us"><span>Contact us</span></a></li>
    </ul></div>
  </div>
  <div id="p-interaction" class="vector-menu mw-portlet mw-portlet-interaction">
    <div class="vector-menu-heading">Contribute</div>
    <div class="vector-menu-content"><ul class="vector-menu-content-list">
      <li><a href="/wiki/Help:Contents"><span>Help</span></a></li>
      <li><a href="/wiki/Help:Introduction"><span>Learn to edit</span></a></li>
      <li><a href="/wiki/Wikipedia:Community_portal"><span>Community portal</span></a></li>
      <li><a href="/wiki/Special:RecentChanges"><span>Recent changes</span></a></li>
      <li><a href="/wiki/Wikipedia:File_upload_wizard"><span>Upload file</span></a></li>
      <li><a href="/wiki/Special:SpecialPages"><span>Special pages</span></a></li>
    </ul></div>
  </div>
</div>
"""

WIKIPEDIA_VECTOR_2022 = f"""<!DOCTYPE html>
<html class="client-nojs vector-feature-main-menu-pinned-disabled" lang="en" dir="ltr">
<head><meta charset="UTF-8"><title>Edible mushroom - Wikipedia</title></head>
<body class="skin--responsive skin-vector skin-vector-2022 mediawiki ltr">
<a class="mw-jump-link" href="#bodyContent">Jump to content</a>
<div class="vector-header-container">
 <header class="vector-header mw-header">
  <div class="vector-header-start">
   <nav class="vector-main-menu-landmark" aria-label="Site">
    <div id="vector-main-menu-dropdown" class="vector-dropdown vector-main-menu-dropdown vector-button-flush-left vector-button-flush-right">
     <input type="checkbox" id="vector-main-menu-dropdown-checkbox" role="button" class="vector-dropdown-checkbox" aria-label="Main menu">
     <label id="vector-main-menu-dropdown-label" for="vector-main-menu-dropdown-checkbox" class="vector-dropdown-label cdx-button" aria-hidden="true"><span class="vector-icon mw-ui-icon-menu"></span><span class="vector-dropdown-label-text">Main menu</span></label>
     <div class="vector-dropdown-content">
      <div id="vector-main-menu-unpinned-container" class="vector-unpinned-container">
       {_MAIN_MENU}
      </div>
     </div>
    </div>
   </nav>
   <a href="/wiki/Main_Page" class="mw-logo"><span class="mw-logo-container"></span></a>
  </div>
  <div class="vector-header-end">
   <div id="p-search" class="vector-search-box-vue vector-search-box">
    <form id="searchform" class="cdx-search-input"><div class="cdx-text-input cdx-text-input--has-start-icon"><input name="search" placeholder="Search Wikipedia"></div><button>Search</button></form>
   </div>
   <nav class="vector-user-links vector-user-links-wide" aria-label="Personal tools">
    <div class="vector-user-links-main">
     <div id="p-vector-user-menu-overflow" class="vector-menu mw-portlet"><div class="vector-menu-content"><ul class="vector-menu-content-list"><li><a href="#">Create account</a></li><li><a href="#">Log in</a></li></ul></div></div>
    </div>
   </nav>
  </div>
 </header>
</div>
<div class="mw-page-container">
 <div class="mw-page-container-inner">
  <div class="vector-sitenotice-container"><div id="siteNotice"></div></div>
  <div class="vector-column-start">
   <div class="vector-main-menu-container"><div id="mw-navigation"><nav id="mw-panel" class="vector-main-menu-landmark" aria-label="Site"><div id="vector-main-menu-pinned-container" class="vector-pinned-container"></div></nav></div></div>
   <div class="vector-sticky-pinned-container">
    <nav id="mw-panel-toc" aria-label="Contents" class="mw-table-of-contents-container vector-toc-landmark">
     <div id="vector-toc" class="vector-toc vector-pinnable-element"><h2 class="vector-pinnable-header-label">Contents</h2>
      <ul class="vector-toc-contents"><li><a href="#">(Top)</a></li><li><a href="#Identification">Identification</a></li><li><a href="#Cultivation">Cultivation</a></li></ul>
     </div>
    </nav>
   </div>
  </div>
  <div class="mw-content-container">
   <main id="content" class="mw-body">
    <header class="mw-body-header vector-page-titlebar">
     <h1 id="firstHeading" class="firstHeading mw-first-heading"><span class="mw-page-title-main">Edible mushroom</span></h1>
     <div id="p-lang-btn" class="vector-dropdown mw-portlet mw-portlet-lang">
      <label id="p-lang-btn-label" class="vector-dropdown-label"><span class="vector-dropdown-label-text">38 languages</span></label>
      <div class="vector-dropdown-content"><div class="vector-menu-content"><ul class="vector-menu-content-list"><li><a lang="de">Deutsch</a></li><li><a lang="fr">Français</a></li></ul></div></div>
     </div>
    </header>
    <div class="vector-page-toolbar">
     <div class="vector-page-toolbar-container">
      <div id="left-navigation"><nav aria-label="Namespaces"><div id="p-associated-pages" class="vector-menu vector-menu-tabs mw-portlet"><div class="vector-menu-content"><ul class="vector-menu-content-list"><li><a href="#">Article</a></li><li><a href="#">Talk</a></li></ul></div></div></nav></div>
      <div id="right-navigation" class="vector-collapsible"><nav aria-label="Views"><div id="p-views" class="vector-menu vector-menu-tabs mw-portlet"><div class="vector-menu-content"><ul class="vector-menu-content-list"><li><a href="#">Read</a></li><li><a href="#">Edit</a></li><li><a href="#">View history</a></li></ul></div></div></nav></div>
     </div>
    </div>
    <div class="vector-column-end"><div class="vector-sticky-pinned-container"></div></div>
    <div id="bodyContent" class="vector-body">
     <div class="vector-body-before-content"><div id="siteSub" class="noprint">From Wikipedia, the free encyclopedia</div></div>
     <div id="mw-content-text" class="mw-body-content">
      <div class="mw-content-ltr mw-parser-output" lang="en" dir="ltr">
       <p><b>Edible mushrooms</b> are the fleshy fruit bodies of numerous species of macrofungi. Edibility may be defined by criteria including the absence of poisonous effects on humans and desirable taste and aroma.</p>
       <div class="mw-heading mw-heading2"><h2 id="Identification">Identification</h2></div>
       <p>Mushroom identification requires a basic understanding of their macroscopic structure. Most are basidiomycetes and gilled.</p>
       <div class="mw-heading mw-heading2"><h2 id="Cultivation">Cultivation</h2></div>
       <p>Commercially cultivated species include the button mushroom, shiitake and oyster mushrooms.</p>
      </div>
     </div>
     <div id="catlinks" class="catlinks"><div id="mw-normal-catlinks" class="mw-normal-catlinks">Categories: Edible fungi</div></div>
    </div>
   </main>
  </div>
  <div class="mw-footer-container">
   <footer id="footer" class="mw-footer"><ul id="footer-info"><li>This page was last edited on 1 October 2026.</li></ul><ul id="footer-places"><li><a href="#">Privacy policy</a></li></ul></footer>
  </div>
 </div>
</div>
</body>
</html>
"""


class _FakeResponse:
    status_code = 200
    headers = {"Content-Type": "text/html; charset=utf-8"}
    content = b""

    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


def _extract(html: str, tmp_path, monkeypatch, url: str) -> str:
    monkeypatch.setattr(service_content, "CONTENT_CACHE_DIR", tmp_path)
    service_content.content_cache_index.clear()
    monkeypatch.setattr(
        service_content,
        "_get_public_url",
        lambda url, headers, timeout, **kwargs: _FakeResponse(html),
    )
    result = service_content.fetch_webpage_content(url)
    assert result["success"], result.get("error")
    return result["content"]


def test_wikipedia_article_text_not_main_menu(tmp_path, monkeypatch):
    text = _extract(WIKIPEDIA_VECTOR_2022, tmp_path, monkeypatch,
                    "https://en.wikipedia.org/wiki/Edible_mushroom")

    assert text != RECORDED_MENU_ONLY_EXTRACT
    assert "fleshy fruit bodies of numerous species" in text, text[:300]
    assert "Commercially cultivated species" in text, text[-300:]
    for menu_text in ("Main menu", "move to sidebar", "Random article", "Create account"):
        assert menu_text not in text, f"site navigation leaked into the extract: {menu_text!r}"


def test_navigation_inside_main_is_dropped(tmp_path, monkeypatch):
    """Wikipedia puts the language menu (in <header>) and the
    Article/Talk/Read/Edit tabs (in <nav>) inside <main>; they are chrome."""
    text = _extract(WIKIPEDIA_VECTOR_2022, tmp_path, monkeypatch,
                    "https://en.wikipedia.org/wiki/Edible_mushroom")

    for chrome in ("38 languages", "Deutsch", "View history", "Privacy policy"):
        assert chrome not in text, f"page chrome leaked into the extract: {chrome!r}"


def test_role_main_counts_as_main_content(tmp_path, monkeypatch):
    html = """<html><head><title>t</title></head><body>
      <div class="main-navigation">Home Products Pricing Blog Careers Contact</div>
      <div role="main"><p>The documented answer lives here. """ + "Detail. " * 100 + """</p></div>
    </body></html>"""
    text = _extract(html, tmp_path, monkeypatch, "https://example.com/role-main")

    assert text.startswith("The documented answer lives here."), text[:120]
    assert "Pricing" not in text


def test_single_article_counts_as_main_content(tmp_path, monkeypatch):
    html = """<html><head><title>t</title></head><body>
      <div class="main-nav">Home Archive About Subscribe</div>
      <article><p>Single post body. """ + "Sentence. " * 100 + """</p></article>
    </body></html>"""
    text = _extract(html, tmp_path, monkeypatch, "https://example.com/one-article")

    assert text.startswith("Single post body."), text[:120]
    assert "Subscribe" not in text


def test_several_articles_keep_the_old_heuristic(tmp_path, monkeypatch):
    """Negative control: a listing page with several <article> elements has no
    single main article, so the class heuristic still decides (first three
    matches, in document order)."""
    posts = "".join(
        f'<article class="post"><p>Post number {i}. ' + "Words. " * 30 + "</p></article>"
        for i in range(1, 5)
    )
    html = f"<html><head><title>t</title></head><body>{posts}</body></html>"
    text = _extract(html, tmp_path, monkeypatch, "https://example.com/listing")

    assert "Post number 1." in text and "Post number 3." in text
    assert "Post number 4." not in text


def test_page_without_main_landmark_is_unchanged(tmp_path, monkeypatch):
    """Negative control: no <main>, role=main or <article> -> class heuristic."""
    html = """<html><head><title>t</title></head><body>
      <div class="sidebar">Sidebar links</div>
      <div class="entry-content"><p>Entry text. """ + "More. " * 150 + """</p></div>
    </body></html>"""
    text = _extract(html, tmp_path, monkeypatch, "https://example.com/no-landmark")

    assert text.startswith("Entry text."), text[:120]
    assert "Sidebar links" not in text


def test_thin_main_still_falls_back_to_body_text(tmp_path, monkeypatch):
    """Negative control: an app-shell <main> with almost no text must not hide
    the page's real text from the existing body fallback."""
    html = """<html><head><title>t</title></head><body>
      <main><p>Loading…</p></main>
      <div id="rendered"><p>Server-rendered fallback copy. """ + "Text. " * 150 + """</p></div>
    </body></html>"""
    text = _extract(html, tmp_path, monkeypatch, "https://example.com/app-shell")

    assert "Server-rendered fallback copy." in text, text[:200]
