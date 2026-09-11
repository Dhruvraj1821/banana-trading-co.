# Banana Trading Company - Design Doc

## Problem Statement

Players start with a fixed amount of in-game currency and trade "cards"
whose prices change based on trading activity and background randomness.
Players can also publish their own cards once they reach a wealth
threshold. The goal is to become the richest player.

The central design problem: prices must respond to real trading activity
and feel alive even when a card isn't being traded, while making it
mathematically hard for a single player to exploit the price mechanism to
generate money without taking on real risk. Everything else in the game
(leaderboard, newspaper, rewards) depends on this being solved correctly
first, so this doc focuses almost entirely on it.

## Goals

- Every card always has a price and can always be bought or sold, even
  with very few active traders.
- A large single trade should cost progressively more per unit (protects
  against one player draining a card cheaply).
- Prices should move on their own between trades, not just sit frozen on
  low-activity cards.
- The system should be provably resistant to basic manipulation
  strategies before real users touch it, not patched after the fact.

## Non-Goals (for v1)

- Real order matching between players (limit orders, order book depth).
- Cross-card arbitrage mechanics.
- Real-money value in any form.

## Pricing Model

### Base mechanism: constant-product reserves

Each card has two internal values:

- `currency_reserve`
- `card_reserve`

```
price = currency_reserve / card_reserve
```

A buy adds currency into the reserve and removes card units from it; a
sell does the opposite. Because the relationship is a ratio, larger trades
move the ratio more, so the average price paid per unit rises as trade
size increases. This gives slippage for free, without a separate rule
needing to be written for it.

Selling back into a card after buying nets less than was paid, once the
trading fee is applied, so simply buying and selling in a loop cannot
generate profit on its own.

### Idle drift (background randomness)

On a fixed interval (for example every few minutes), every card gets a
small random adjustment to its reserves, independent of whether anyone
traded it:

```
drift = random(mean=0, stdev=base_volatility)
drift += momentum_weight * recent_net_demand(card)
currency_reserve *= (1 + drift)
```

`base_volatility` is set higher for cards with little recent trading, so
dormant cards still move, and lower for cards with a lot of real trading,
so their price stays mostly driven by actual demand. The drift is clamped
per tick so it can't itself cause a large price swing on an illiquid
card.

### Fees

Every trade takes a small fee (fee_rate=0.01, see Tuning Results below),
split three ways:

- a share to the card's creator, as an ongoing incentive to publish good
  cards
- a share burned (removed from the economy entirely), to offset currency
  added through daily rewards and prevent long-term inflation
- a share into a treasury fund, used for leaderboard rewards and event
  prizes

### Anti-whale rules on top of the base model

The reserve math already discourages large single trades through
slippage. Two more rules on top of it:

- a hard cap on how much of a card's total supply one player can hold at
  once (cap_pct=0.20, see Tuning Results below), checked against a fixed
  total supply set at the card's launch, not a growing circulating supply
  (a growing denominator creates a bootstrapping deadlock where the first
  buyer always owns 100% of whatever exists so far, blocking any cap
  below 100% before a single trade can happen)
- a fee rate that increases above a configured trade size threshold
  (not yet implemented, see Open Questions)

These exist mainly as a backstop in case the base curve parameters are
tuned in a way that leaves a gap, not as the primary defense, though
simulation shows both mechanisms independently provide real protection
(see below).

## Why this model instead of an order book

An order book needs real liquidity on both sides to work well. Most cards
in this game will have a small number of active traders, so an order
book would often be empty or too thin to fill trades reasonably, and thin
books are also easier to manipulate through spoofing. A reserve-based
model guarantees a price and fillable liquidity at all times, and the
same mechanism that gives it liquidity also produces the slippage needed
to resist whale manipulation, so the two requirements are solved by one
piece of math instead of two separate systems.

## Failure Modes Considered

- **Whale draining a card in one trade**: blocked by slippage, since the
  cost per unit rises as the trade grows. Confirmed by simulation (see
  Tuning Results).
- **Wash trading (buying and selling repeatedly to manufacture fake
  volume)**: fees make this a guaranteed loss on its own, so it costs the
  player money rather than making them any. Confirmed by simulation.
- **Splitting one large buy into many small ones to dodge the ownership
  cap**: the cap tracks cumulative holdings per player, not per-trade
  size, so splitting doesn't raise the effective ceiling. Confirmed by
  simulation.
- **Currency inflation from daily rewards**: offset by the burn portion
  of trading fees; needs to be checked against real reward numbers once
  those are set in a later phase, not assumed to balance automatically.
- **Manipulating a dormant, low-liquidity card cheaply**: idle drift is
  clamped per tick, and ownership caps limit how much of a thin card any
  one player can control.
- **Concurrent trades on the same card causing an inconsistent price**:
  every card's reserve state is only ever updated by one serialized
  writer, so two trades landing at the same time can't race each other.
  (Enforced at the application level in Phase 1; Phase 2 implements this
  at the database level with row-level locking.)

## Tuning Results (from Phase 1 simulation)

`fee_rate=0.01` and `cap_pct=0.20` were validated against three
adversarial scenarios, run against a pool with `currency_reserve=100,000`
and `card_reserve=10,000`:

- **Single big buy (50,000 currency, half the pool)**: fully blocked by
  the ownership cap before slippage even comes into play (would have
  landed the whale at 3,311 units, 33% of total supply, against a
  2,000-unit / 20% cap).
- **Same attack with the cap effectively disabled**: the trade goes
  through, but at a 51% price premium over the starting price (average
  15.10 vs a starting price of 10.0), confirming slippage alone is a
  real, independent defense, not just a theoretical one.
- **Split-buy cap evasion (100 chunks of 500 currency each)**: blocked at
  50 successful chunks, landing at 1,983.97 units, 99.2% of the cap, the
  same ceiling a single large trade would hit. Splitting does not raise
  the effective limit.
- **Wash trading (50 cycles, 200 currency each)**: guaranteed net loss of
  ~199 currency total (~4 per cycle), matching the expected ~2%
  round-trip cost of a 1% fee applied on both the buy and the sell.

These results confirm the two anti-whale mechanisms are genuinely
layered rather than redundant: the cap acts as a deterministic ceiling,
while slippage independently punishes large trades even in scenarios
where the cap alone wouldn't have been tight enough. These are the
confirmed default values going into Phase 2.

## Phase 3: Creator Stake Fairness (exploit write-up)

A creator retaining a stake in their own card could plausibly extract
unfair value if that stake were exempt from the same rules other holders
face. Two properties were verified with automated tests:

- A creator's stake is checked against the ownership cap **at the same
  percentage as any other holder**, at both creation time (stake cannot
  exceed the cap) and in every subsequent trade. A creator holding the
  maximum allowed 20% stake cannot buy a single additional unit, the
  cap blocks it exactly as it would a whale's attempted purchase.
- Selling a creator's stake executes through the same constant-product
  curve as any sell, there is no fixed-price or privileged redemption
  path. Liquidating a full stake in one trade measurably drops the
  price via the same slippage mechanism that punishes any large sale.

Combined with the currency conservation test (system-wide currency
strictly decreases by exactly the burn amount across any batch of
trades, never drifts up), this closes out Phase 3's core fairness
requirement: creator stake is a real economic incentive, not a backdoor.

## Architecture (initial pass)

- FastAPI backend, async
- Postgres for the trade ledger and user/card state, run locally via
  Docker Compose during development (mapped to host port 5433 to avoid
  conflicting with a pre-existing local Postgres install), RDS on AWS
  free tier in deployment
- Redis for price caching and pub/sub, running as a container alongside
  the API
- WebSockets for pushing live price updates to clients
- Background worker process for the drift tick, leaderboard
  recalculation, and newspaper generation
- Deployed as Docker containers on a single EC2 instance (free tier),
  with Nginx handling HTTPS in front of it
- Frontend as a static React build, likely served from S3 and CloudFront

## Open Questions

- Whether fixed-supply and unlimited-supply cards need different curve
  parameters, since an unlimited supply model changes what "cornering the
  market" even means.
- How aggressive the momentum term should be before it starts feeling
  like it's picking winners rather than reflecting real demand.
- Whether the progressive fee-above-threshold rule is worth implementing
  given the cap and slippage already provide layered protection, or
  whether it's unnecessary complexity, to be revisited after Phase 2's
  concurrency work.