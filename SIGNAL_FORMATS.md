# Gauls Signal Format Documentation

## Known Signal Formats

The system must handle ALL of these variations:

### 1. Symbol Formats
- **WITH dollar sign**: `$BTC`, `$ETH`, `$SEI`  
- **WITHOUT dollar sign**: `BTC`, `ETH`, `SEI`
- **Parser regex**: `\$?([A-Z]{2,10})`

### 2. Setup Formats
- `Buying Setup:` (capitalized)
- `buying setup:` (lowercase)
- `Spot/Swing Buying Setup:`

### 3. Entry Formats
- `Entry: CMP` (Current Market Price)
- `Entry: 111216` (specific price)
- `Entry: 111216 (A bit above)` (with hint)
- `👉 Entry: CMP` (with emoji)
- `Entry : CMP` (with space before colon)

### 4. Take Profit Formats
- `TP: 114786`
- `Target: 114786`
- `👉 TP: 114786` (with emoji)
- `TP : 114786` (with space)

### 5. Stop Loss Formats
- `SL: 111468`
- `Invalidation: 111468`
- `👉 SL: 111468` (with emoji)
- `SL : 111468` (with space)

## Parser Output Format

The parser returns a dictionary with these keys:
- `symbol`: "BTC/USDT" (always adds /USDT)
- `entry_price`: float or "CMP"
- `entry_type`: "market" or "limit"
- `entry_hint`: "A bit above" (optional)
- `take_profit`: float
- `stop_loss`: float
- `risk_reward`: float (optional)
- `raw_text`: original message

## Example Signals

### Standard Format
```
$BTC Buying Setup:

👉 Entry: CMP
👉 TP: 114786
👉 SL: 111468
```

### Without Dollar Sign (MUST HANDLE!)
```
BTC Buying Setup:

👉 Entry: CMP
👉 TP: 114786
👉 SL: 111468
```

### Spot/Swing Format
```
$SEI Spot/Swing Buying Setup:

👉 Entry: CMP till 2780
👉 TP: 0.43
👉 SL: 0.26
```

### With Entry Hint
```
$AI Buying Setup:

👉 Entry: 0.14 (A bit above)
👉 TP: 0.16
👉 SL: 0.12
```

## SQL Query Patterns

The scanner uses these patterns to find signals:

```sql
WHERE (message_text LIKE '%Setup%' OR message_text LIKE '%setup%')
  AND (message_text LIKE '%Entry:%' OR message_text LIKE '%Entry :%' OR message_text LIKE '%Entry: %')
  AND (message_text LIKE '%TP:%' OR message_text LIKE '%Target:%' OR message_text LIKE '%TP: %')
  AND (message_text LIKE '%SL:%' OR message_text LIKE '%Invalidation:%' OR message_text LIKE '%SL: %')
```

## Why The Bug Happened

1. **Assumption**: Code assumed all signals had `$` prefix
2. **Reality**: Gauls sometimes omits the `$` 
3. **Fix**: Made `$` optional in regex: `\$?([A-Z]{2,10})`
4. **Testing Gap**: No tests covered format variations

## Prevention

1. **Unit Tests**: Test ALL format variations
2. **Integration Tests**: Test full signal flow
3. **Monitoring**: Log when signals are parsed/skipped
4. **Defensive Coding**: Handle variations gracefully