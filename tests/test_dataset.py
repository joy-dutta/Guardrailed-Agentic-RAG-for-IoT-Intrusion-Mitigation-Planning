from iot_poc.dataset import attack_family


def test_official_attack_folders_map_to_expected_families() -> None:
    assert attack_family("Benign_Final") == "Benign"
    assert attack_family("DDoS-UDP_Flood") == "DDoS"
    assert attack_family("DoS-TCP_Flood") == "DoS"
    assert attack_family("Recon-PortScan") == "Recon"
    assert attack_family("Mirai-greeth_flood") == "Mirai"
    assert attack_family("DictionaryBruteForce") == "BruteForce"
    assert attack_family("MITM-ArpSpoofing") == "Spoofing"
    assert attack_family("SqlInjection") == "Web"
