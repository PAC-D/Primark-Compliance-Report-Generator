from tps.reports import pdf


class FakePlaywright:
    started = 0
    close_raises = False

    def __init__(self):
        self.chromium = self

    def start(self):
        FakePlaywright.started += 1
        return self

    def launch(self, headless):
        return FakeBrowser()

    def stop(self):
        pass


class FakeBrowser:
    def new_page(self, viewport):
        return FakePage()

    def close(self):
        if FakePlaywright.close_raises:
            raise RuntimeError("boom")


class FakePage:
    pass


def _fresh(monkeypatch):
    monkeypatch.setattr(pdf, "sync_playwright", FakePlaywright)
    monkeypatch.setattr(pdf, "_local", type(pdf._local)())
    FakePlaywright.started, FakePlaywright.close_raises = 0, False


def test_browser_relaunches_after_recycle_after_renders(monkeypatch):
    _fresh(monkeypatch)
    for _ in range(pdf.RECYCLE_AFTER):
        pdf._page()
        pdf._local.renders += 1
    assert FakePlaywright.started == 1
    pdf._page()
    assert FakePlaywright.started == 2 and pdf._local.renders == 0


def test_failed_close_still_resets_state(monkeypatch):
    _fresh(monkeypatch)
    pdf._page()
    pdf._local.renders = pdf.RECYCLE_AFTER
    FakePlaywright.close_raises = True
    try:
        pdf._page()
    except RuntimeError:
        pass
    FakePlaywright.close_raises = False
    pdf._page()  # relaunches instead of raising again
    assert FakePlaywright.started == 2 and pdf._local.renders == 0
