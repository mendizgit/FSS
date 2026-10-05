from tss.control.flags import news_on, telegram_on


def test_news_defaults_to_on_and_follows_the_flag() -> None:
    assert news_on({})
    assert not news_on({"news": False})
    assert news_on({"news": True})


def test_telegram_needs_credentials_whatever_the_flag_says() -> None:
    assert not telegram_on({"telegram": True}, configured=False, env_paused=False)


def test_telegram_env_decides_until_the_dashboard_overrides_it() -> None:
    assert telegram_on({}, configured=True, env_paused=False)
    assert not telegram_on({}, configured=True, env_paused=True)
    assert telegram_on({"telegram": True}, configured=True, env_paused=True)
    assert not telegram_on({"telegram": False}, configured=True, env_paused=False)
