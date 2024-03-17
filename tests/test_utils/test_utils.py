from aprs_backend.utils import check_object_store_config


def test_check_object_store_config(subtests):
    class TestingConfig:
        BOT_DATA_DIR = "testing"
        pass

    for kwarg, config_key in {
        "enable_save": "APRS_PACKET_STORE_ENABLE_SAVE",
        "save_location": "APRS_PACKET_STORE_SAVE_LOCATION",
        "aprs_packet_store_filename_prefix": "APRS_PACKET_STORE_FILENAME_PREFIX",
        "aprs_packet_store_filename_suffix": "APRS_PACKET_STORE_FILENAME_SUFFIX",
        "aprs_packet_store_file_extension": "APRS_PACKET_STORE_FILE_EXTENSION",
    }.items():
        with subtests.test(f"Testing {config_key}-{kwarg}"):
            testing_config = TestingConfig()
            setattr(testing_config, config_key, "testing")
            result = check_object_store_config(testing_config)
            assert kwarg in result
            assert result[kwarg] == "testing"
