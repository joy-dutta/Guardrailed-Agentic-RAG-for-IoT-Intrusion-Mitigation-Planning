import pandas as pd

from iot_poc.split_protocols import assign_attack_type_aware, three_way_file_split


def test_three_way_file_split_is_complete_disjoint_and_nonempty() -> None:
    files = [f"attack/file-{index}.csv" for index in range(7)]
    splits = three_way_file_split(files, seed=42)

    split_sets = {name: set(values) for name, values in splits.items()}
    assert all(split_sets.values())
    assert set.union(*split_sets.values()) == set(files)
    assert split_sets["train"].isdisjoint(split_sets["calibration"])
    assert split_sets["train"].isdisjoint(split_sets["test"])
    assert split_sets["calibration"].isdisjoint(split_sets["test"])


def test_attack_type_aware_split_holds_files_out_when_possible() -> None:
    rows = []
    for file_index in range(3):
        for source_row in range(2):
            rows.append(
                {
                    "attack_type": "multi-file-attack",
                    "source_file": f"multi/file-{file_index}.csv",
                    "source_row": source_row,
                }
            )
    for source_row in range(10):
        rows.append(
            {
                "attack_type": "single-file-attack",
                "source_file": "single/only.csv",
                "source_row": source_row,
            }
        )
    frame = pd.DataFrame(rows)

    assignments, audit = assign_attack_type_aware(frame, seed=7)
    frame = frame.assign(split=assignments)

    multi = frame[frame["attack_type"] == "multi-file-attack"]
    file_split_counts = multi.groupby("source_file")["split"].nunique()
    assert (file_split_counts == 1).all()
    assert set(multi["split"]) == {"train", "calibration", "test"}
    assert (
        audit["multi-file-attack"]["method"]
        == "file_disjoint_within_attack_type"
    )

    single = frame[frame["attack_type"] == "single-file-attack"]
    assert list(single["split"]) == ["train"] * 6 + ["calibration"] * 2 + ["test"] * 2
    assert (
        audit["single-file-attack"]["method"]
        == "ordered_row_blocks_due_to_fewer_than_three_files"
    )
