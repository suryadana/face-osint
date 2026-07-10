from modules.instagram import parse_profile_media


def _api(user):
    return {"data": {"user": user}}


def test_parse_extracts_pic_and_posts():
    user = {
        "hd_profile_pic_url_info": {"url": "https://cdn/hd.jpg"},
        "profile_pic_url": "https://cdn/lo.jpg",
        "edge_owner_to_timeline_media": {"edges": [
            {"node": {"display_url": "https://cdn/p1.jpg"}},
            {"node": {"display_url": "https://cdn/p2.jpg"}},
        ]},
    }
    out = parse_profile_media(_api(user))
    assert out["profile_pic_url"] == "https://cdn/hd.jpg"      # hd preferred
    assert out["post_urls"] == ["https://cdn/p1.jpg", "https://cdn/p2.jpg"]


def test_parse_falls_back_to_lo_pic_and_empty_posts():
    out = parse_profile_media(_api({"profile_pic_url": "https://cdn/lo.jpg"}))
    assert out["profile_pic_url"] == "https://cdn/lo.jpg"
    assert out["post_urls"] == []


def test_parse_handles_missing_user():
    out = parse_profile_media({"data": {}})
    assert out == {"profile_pic_url": None, "post_urls": []}
