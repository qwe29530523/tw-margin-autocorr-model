from src.common.settings import load_settings


def test_load_settings_respects_mock_mode_false_even_when_optional_keys_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("FRED_API_KEY", "fred-test-key")
    monkeypatch.setenv("EIA_API_KEY", "eia-test-key")
    monkeypatch.delenv("BLS_API_KEY", raising=False)

    settings = load_settings()

    assert settings.mock_mode is False
    assert settings.fred_api_key == "fred-test-key"
    assert settings.eia_api_key == "eia-test-key"
    assert settings.bls_api_key is None


def test_load_settings_reads_dotenv_from_current_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MOCK_MODE", raising=False)
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    monkeypatch.delenv("BLS_API_KEY", raising=False)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "MOCK_MODE=false",
                "FRED_API_KEY=fred-from-dotenv",
                "EIA_API_KEY=eia-from-dotenv",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings()

    assert settings.env_file_loaded is True
    assert settings.env_file_path == str(tmp_path / ".env")
    assert settings.mock_mode is False
    assert settings.fred_api_key == "fred-from-dotenv"
    assert settings.eia_api_key == "eia-from-dotenv"
