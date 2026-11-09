"""The login steps Telegram can ask for that have no code path of their own in a simple flow."""
from foxygram.telegram.session import TelegramSession


class RecordingClient:
    def __init__(self, on_update):
        self.calls = []

    async def call(self, query, timeout=60.0):
        self.calls.append(query)
        return {"@type": "ok"}


def session_for(config):
    return TelegramSession(config, client_factory=RecordingClient)


async def test_a_paid_login_is_reported_instead_of_hanging(config):
    session = session_for(config)
    await session._on_auth({"@type": "authorizationStateWaitPremiumPurchase", "store_product_id": "x"})
    assert session.auth.state == "payment_required"


async def test_paid_login_can_still_switch_to_qr(config):
    session = session_for(config)
    await session._on_auth({"@type": "authorizationStateWaitPremiumPurchase", "store_product_id": "x"})
    await session.login_qr()
    assert session.client.calls[-1]["@type"] == "requestQrCodeAuthentication"


async def test_a_code_delivered_inside_telegram_is_flagged(config):
    session = session_for(config)
    await session._on_auth({
        "@type": "authorizationStateWaitCode",
        "code_info": {"phone_number": "+100", "type": {"@type": "authenticationCodeTypeTelegramMessage", "length": 5}},
    })
    assert session.auth.state == "need_code"
    assert session.auth.code_in_telegram is True


async def test_an_sms_code_is_not_flagged(config):
    session = session_for(config)
    await session._on_auth({
        "@type": "authorizationStateWaitCode",
        "code_info": {"phone_number": "+100", "type": {"@type": "authenticationCodeTypeSms", "length": 5}},
    })
    assert session.auth.code_in_telegram is False
