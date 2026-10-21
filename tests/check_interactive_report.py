"""Browser smoke check for rendered HTML (requires Python Playwright + Chromium).

Run: .venv/bin/python tests/check_interactive_report.py
Render both HTML reports first. Charts must work offline, including file:// URLs.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path="/usr/bin/chromium", headless=True)
    for year in (2025, 2026):
        context = browser.new_context(offline=True, viewport={"width": 1280, "height": 900})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto((root / f"{year}_Health_Inspections_Interactive.html").as_uri())
        page.wait_for_selector(".followup-details select")
        assert page.locator(".js-plotly-plot").count() == 6
        details = page.locator(".followup-details")
        assert page.evaluate("""() => {
          const panel = document.querySelector('.followup-details');
          const el = document.getElementById(panel.id.replace(/-details$/, ''));
          return panel.getBoundingClientRect().top >= el.querySelector('.svg-container').getBoundingClientRect().bottom;
        }"""), "The chart must not cover the restaurant selector"
        # Exercise the Plotly hover/click events on a real rendered bubble.
        point = page.evaluate("""() => {
          const panel = document.querySelector('.followup-details');
          const el = document.getElementById(panel.id.replace(/-details$/, ''));
          let chosen;
          el.data.forEach((trace, curve) => {
            (trace.customdata || []).forEach((key, index) => {
              const size = Array.isArray(trace.marker.size) ? trace.marker.size[index] : trace.marker.size;
              if (!chosen || size > chosen.size) chosen = {key, curve, index, size};
            });
          });
          Plotly.Fx.hover(el, [{curveNumber: chosen.curve, pointNumber: chosen.index}]);
          el.emit('plotly_click', {points: [{customdata: chosen.key}]});
          return chosen;
        }""")
        assert "Initial score:" in page.locator(".hoverlayer").last.text_content()
        cards = details.locator("article")
        assert cards.count() >= 1, point
        assert cards.locator("a").count() == cards.count() * 2
        for link in cards.locator("a").all():
            assert link.get_attribute("href").startswith(("http://", "https://"))
        # The same-coordinate list must contain every facility, not just one.
        expected_count = round((point["size"] / 10) ** 2)
        assert cards.count() == expected_count, (cards.count(), expected_count)
        select = details.locator("select")
        first_name = select.locator("option").nth(1).inner_text().split(" | ")[0]
        select.select_option("0")
        assert cards.count() == 1
        assert cards.locator("h4").inner_text() == first_name
        select.select_option("")
        assert cards.count() == 0
        # Also exercise actual pointer interaction on an isolated high-Y point.
        page.locator(".js-plotly-plot").last.scroll_into_view_if_needed()
        target = page.evaluate("""() => {
          const el = document.querySelectorAll('.js-plotly-plot')[5];
          let chosen;
          el.data.forEach(trace => (trace.customdata || []).forEach((key, i) => {
            if (!chosen || trace.y[i] > chosen.y) chosen = {x: trace.x[i], y: trace.y[i], key};
          }));
          const box = el.getBoundingClientRect(), axes = el._fullLayout;
          return {x: box.x + axes.xaxis._offset + axes.xaxis.l2p(chosen.x),
                  y: box.y + axes.yaxis._offset + axes.yaxis.l2p(chosen.y)};
        }""")
        page.mouse.click(target["x"], target["y"])
        assert cards.count() >= 1
        # Mobile layout and the accessible selector remain usable.
        page.set_viewport_size({"width": 390, "height": 844})
        select.select_option("0")
        assert cards.count() == 1
        assert not errors, errors
        print(f"{year}: six offline charts, hover, shared-bubble click, report links, and mobile selection passed.")
        context.close()
    browser.close()
