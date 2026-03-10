"""
Setup SIP telephony for HANA Sentinel voice agent.

This script configures LiveKit Cloud to accept inbound phone calls
and route them to the voice agent. Run once to set up, then callers
can dial the number from the LiveKit Cloud dashboard.

Usage:
    python voice_agent/setup_sip.py          # Create trunk + dispatch rule
    python voice_agent/setup_sip.py --list   # List existing config
    python voice_agent/setup_sip.py --clean  # Remove all SIP config
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

# Load env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "https://blazer-eokti6f6.livekit.cloud")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
    print("Error: LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set in .env")
    sys.exit(1)


async def list_config():
    """List existing SIP trunks and dispatch rules."""
    from livekit.api import (
        LiveKitAPI,
        ListSIPInboundTrunkRequest,
        ListSIPDispatchRuleRequest,
    )

    api = LiveKitAPI(url=LIVEKIT_URL, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)

    trunks_resp = await api.sip.list_inbound_trunk(ListSIPInboundTrunkRequest())
    rules_resp = await api.sip.list_dispatch_rule(ListSIPDispatchRuleRequest())
    await api.aclose()

    trunks = list(trunks_resp.items) if hasattr(trunks_resp, "items") else []
    rules = list(rules_resp.items) if hasattr(rules_resp, "items") else []

    print(f"\n{'='*50}")
    print(f"  SIP Configuration — {LIVEKIT_URL}")
    print(f"{'='*50}")

    if trunks:
        print(f"\nInbound Trunks ({len(trunks)}):")
        for t in trunks:
            print(f"  ID:      {t.sip_trunk_id}")
            print(f"  Name:    {t.name}")
            print(f"  Numbers: {list(t.numbers)}")
            print(f"  Krisp:   {t.krisp_enabled}")
            print()
    else:
        print("\nNo inbound trunks configured.")

    if rules:
        print(f"Dispatch Rules ({len(rules)}):")
        for r in rules:
            print(f"  ID:       {r.sip_dispatch_rule_id}")
            print(f"  Name:     {r.name}")
            print(f"  Trunks:   {list(r.trunk_ids)}")
            if r.rule.HasField("dispatch_rule_individual"):
                print(f"  Type:     Individual (prefix={r.rule.dispatch_rule_individual.room_prefix})")
            elif r.rule.HasField("dispatch_rule_direct"):
                print(f"  Type:     Direct (room={r.rule.dispatch_rule_direct.room_name})")
            print()
    else:
        print("No dispatch rules configured.")

    print()


async def setup():
    """Create an inbound SIP trunk and dispatch rule for the voice agent."""
    from livekit.api import (
        LiveKitAPI,
        CreateSIPInboundTrunkRequest,
        SIPInboundTrunkInfo,
        CreateSIPDispatchRuleRequest,
        SIPDispatchRuleInfo,
        SIPDispatchRule,
        SIPDispatchRuleIndividual,
        ListSIPInboundTrunkRequest,
        ListSIPDispatchRuleRequest,
    )

    api = LiveKitAPI(url=LIVEKIT_URL, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)

    # Check if already configured
    trunks_resp = await api.sip.list_inbound_trunk(ListSIPInboundTrunkRequest())
    existing_trunks = list(trunks_resp.items) if hasattr(trunks_resp, "items") else []
    sentinel_trunks = [t for t in existing_trunks if t.name == "HANA Sentinel"]

    if sentinel_trunks:
        print(f"Trunk already exists: {sentinel_trunks[0].sip_trunk_id}")
        trunk = sentinel_trunks[0]
    else:
        # Create inbound trunk — LiveKit Cloud provides the SIP endpoint.
        # allowed_addresses=["0.0.0.0/0"] allows calls from any SIP provider.
        # You can restrict this later to specific provider IPs for security.
        trunk_info = SIPInboundTrunkInfo(
            name="HANA Sentinel",
            allowed_addresses=["0.0.0.0/0"],
            krisp_enabled=True,  # Noise cancellation for phone calls
        )
        trunk = await api.sip.create_inbound_trunk(
            CreateSIPInboundTrunkRequest(trunk=trunk_info)
        )
        print(f"Created inbound trunk: {trunk.sip_trunk_id}")

    # Check for existing dispatch rule
    rules_resp = await api.sip.list_dispatch_rule(ListSIPDispatchRuleRequest())
    existing_rules = list(rules_resp.items) if hasattr(rules_resp, "items") else []
    sentinel_rules = [r for r in existing_rules if r.name == "HANA Sentinel Voice Agent"]

    if sentinel_rules:
        print(f"Dispatch rule already exists: {sentinel_rules[0].sip_dispatch_rule_id}")
    else:
        # Individual dispatch rule: each phone call gets its own room
        # with prefix "sip-call-" so the agent can identify SIP sessions
        rule = await api.sip.create_dispatch_rule(
            CreateSIPDispatchRuleRequest(
                name="HANA Sentinel Voice Agent",
                trunk_ids=[trunk.sip_trunk_id],
                rule=SIPDispatchRule(
                    dispatch_rule_individual=SIPDispatchRuleIndividual(
                        room_prefix="sip-call-",
                    )
                ),
            )
        )
        print(f"Created dispatch rule: {rule.sip_dispatch_rule_id}")

    await api.aclose()

    print("\nSIP setup complete!")
    print("Next steps:")
    print("  1. Go to https://cloud.livekit.io → your project → Telephony")
    print("  2. Purchase or assign a phone number to the trunk")
    print("  3. Callers dial that number → routed to your voice agent")
    print()


async def clean():
    """Remove all SIP trunks and dispatch rules."""
    from livekit.api import (
        LiveKitAPI,
        ListSIPInboundTrunkRequest,
        ListSIPDispatchRuleRequest,
        DeleteSIPDispatchRuleRequest,
        DeleteSIPTrunkRequest,
    )

    api = LiveKitAPI(url=LIVEKIT_URL, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)

    rules_resp = await api.sip.list_dispatch_rule(ListSIPDispatchRuleRequest())
    rules = list(rules_resp.items) if hasattr(rules_resp, "items") else []
    for r in rules:
        await api.sip.delete_dispatch_rule(
            DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=r.sip_dispatch_rule_id)
        )
        print(f"Deleted dispatch rule: {r.sip_dispatch_rule_id}")

    trunks_resp = await api.sip.list_inbound_trunk(ListSIPInboundTrunkRequest())
    trunks = list(trunks_resp.items) if hasattr(trunks_resp, "items") else []
    for t in trunks:
        await api.sip.delete_trunk(
            DeleteSIPTrunkRequest(sip_trunk_id=t.sip_trunk_id)
        )
        print(f"Deleted trunk: {t.sip_trunk_id}")

    await api.aclose()
    print("All SIP config removed.")


if __name__ == "__main__":
    if "--list" in sys.argv:
        asyncio.run(list_config())
    elif "--clean" in sys.argv:
        asyncio.run(clean())
    else:
        asyncio.run(setup())
