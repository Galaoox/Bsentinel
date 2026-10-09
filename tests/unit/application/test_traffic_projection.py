from bsentinel.domain import traffic


def test_projection_states_sample_and_assumptions():
    result = traffic.project_traffic(
        sample_operations=2, mean_bytes=300, relation_count=3, relation_count_source="requested"
    )
    assert result["bytes_24h"] == 1800
    assert result["bytes_30d"] == 54000
    assert result["sample_operations"] == 2
    assert result["relation_count_source"] == "requested"
    assert result["assumptions"]


def test_projection_without_sample_never_fabricates_zero():
    result = traffic.project_traffic(
        sample_operations=0,
        mean_bytes=None,
        relation_count=3,
        relation_count_source="current_dataset",
    )
    assert result["status"] == "insufficient_sample"
    assert result["bytes_24h"] is None
