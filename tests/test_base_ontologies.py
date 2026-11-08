"""Four base schools + syncretism weighted combos."""


def test_four_base_ontologies():
    from engine.packets import (
        BASE_PACKET_IDS,
        BASE_SCHOOLS,
        COURT_MIXES,
        PACKET_CATALOG,
        court_base_mix,
        expand_to_base_schools,
        starting_weights,
    )

    assert set(BASE_SCHOOLS) == {"legalism", "mohism", "daoism", "confucianism"}
    assert BASE_PACKET_IDS == {
        "legalist_fa",
        "mohist_shangxian",
        "dao_guodian",
        "ru_li",
    }
    for bid in BASE_PACKET_IDS:
        assert PACKET_CATALOG[bid].kind == "base"
    assert PACKET_CATALOG["huang_lao"].kind == "syncretism"
    assert PACKET_CATALOG["guanzi"].kind == "syncretism"
    hl = PACKET_CATALOG["huang_lao"].blend_weights
    gz = PACKET_CATALOG["guanzi"].blend_weights
    assert hl["daoism"] > hl["legalism"]
    assert gz["legalism"] > gz["daoism"]
    qin_base = court_base_mix("qin")
    assert qin_base["legalism"] > qin_base["daoism"]
    assert abs(sum(qin_base.values()) - 1.0) < 0.02
    rolled = expand_to_base_schools({"huang_lao": 1.0})
    assert rolled["mohism"] == 0.0 and rolled["confucianism"] == 0.0
    assert rolled["daoism"] > 0 and rolled["legalism"] > 0
    assert len(starting_weights("chu")) >= 4
    # Every court holds a multi-packet mix (bases + syncretisms + overlays)
    for sid, mix in COURT_MIXES.items():
        assert len(mix) >= 3, sid
        bases = expand_to_base_schools(mix)
        assert abs(sum(bases.values()) - 1.0) < 0.05 or sum(bases.values()) > 0.2
