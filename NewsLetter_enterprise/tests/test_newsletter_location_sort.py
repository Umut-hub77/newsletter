from app.newsletter import sort_news_for_location


class FakeNewsItem:
    def __init__(self, title: str, summary: str | None = None):
        self.title = title
        self.summary = summary


def test_sort_news_for_location_prioritizes_local_matches():
    items = [
        FakeNewsItem("Dünya Ekonomisi güncel"),
        FakeNewsItem("İstanbul'da trafik yoğunluğu"),
        FakeNewsItem("Teknoloji haberleri"),
    ]

    ordered = sort_news_for_location(items, "İstanbul")

    assert ordered[0].title == "İstanbul'da trafik yoğunluğu"
    assert ordered[1].title == "Dünya Ekonomisi güncel"


def test_sort_news_for_location_keeps_original_order_without_location():
    items = [
        FakeNewsItem("Birinci haber"),
        FakeNewsItem("İkinci haber"),
    ]

    ordered = sort_news_for_location(items, None)

    assert [item.title for item in ordered] == ["Birinci haber", "İkinci haber"]
