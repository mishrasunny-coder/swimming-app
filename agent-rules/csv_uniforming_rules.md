# CSV Uniforming Rules (Agent Handoff)

Use this guide to apply the same normalization decisions we used in this project.
Target file for pre-validation work: `codex/copy_of_swim_data.csv`.
Only sync to `CSV/swim_data.csv` after validation.

## 1) Safety Rules
- Do not delete rows.
- Do not add rows during uniforming (parser runs can add rows; uniforming should not).
- Keep the same CSV columns and order.
- After any mapping, verify row count is unchanged.

## 2) Event_Type Normalization

### Age-band standard
- Convert all `X & Under` variants to `X&U`.
- Convert all `X & Over` variants to `X&O`.
- Convert `Year Olds` wording into `&U` form.

Examples:
- `Girls 8 & Under 25 Yard Freestyle` -> `Girls 8&U 25 Yard Freestyle`
- `Boys 10 & Under 100 Yard IM` -> `Boys 10&U 100 Yard IM`
- `Boys 8 Year Olds 25 Yard Backstroke` -> `Boys 8&U 25 Yard Backstroke`

### Requested grouping rules
- Girls: any `Girls 6`, `Girls 7`, `Girls 8` -> `Girls 8&U`
- Girls: any `Girls 9`, `Girls 9-10`, `Girls 10` -> `Girls 10&U`
- Boys: any `Boys 9`, `Boys 9-10`, `Boys 10` -> `Boys 10&U`
- Same concept for `Female/Male/Women/Men` labels when age is 9/10: normalize to `10&U`.

Do not remap ranges like `9-12`, `11-12`, `13-14`, `15-18`, or `9&O`.

### Stroke naming standard
Use only these stroke words:
- `Freestyle`
- `Backstroke`
- `Breaststroke`
- `Butterfly`

Examples:
- `25 Yard Free` -> `25 Yard Freestyle`
- `25 Yard Back` -> `25 Yard Backstroke`

## 3) Team Normalization (Alias -> Canonical)

Use canonical names below:
- `RVYM-NJ` -> `Raritan Valley YMCA Riptide-NJ`
- `WY -NJ` -> `Westfield Area Y Devilfish-NJ`
- `RY -NJ` -> `Ridgewood YMCA Breakers Swim T-NJ`
- `BRKSD` -> `Brookside Swim Team`
- `MEY -NJ` and `Metuchen-Edison/South Amboy` variants -> `Metuchen-Edison/South Amboy YM-NJ`
- `PRY` and truncated Princeton variants -> `The Princeton YMCA Pirates Swim`
- `MDY -NJ` -> `Meadowlands Sharks-NJ`
- `SHSC` -> `Somerset Hills Swim Club`
- `GSCY` -> `Greater Somerset County YMCA`
- `Bergen` / `BB` -> `Bergen Barracudas`
- `CG` -> `College Green Gators`
- `X-Cel` -> `X-cel`
- `Ace` -> `Ace Swim Team-NJ`
- `Apex` -> `Apex Swim Club-NJ`
- `Whitewaters` -> `Whitewaters Swimming-NJ`
- `Genesis` -> `Genesis Riptide Swim Team-NJ`
- `Peddie` -> keep as `Peddie`
- `Scarlet` -> `Scarlet Aquatics-NJ`

## 4) Name Normalization
- If swimmer names appear as `Last, First`, convert to `First Last`.
- This was specifically required for BB Snowflake-style rows (example: `Mishra, Siya` -> `Siya Mishra`).

## 5) Relay/Status Handling Rules
- Do not drop exhibition rows (`X`) or exhibition events.
- Do not drop rows with relay swimmer counts < 4.
- Do not drop statuses like `DQ`, `DNS`, `NS`, `DNF`, `DW`.
- Preserve all result rows; normalization should change labels only.

## 6) Validation Checklist (Run Every Time)
- Row count before == row count after.
- No unexpected new nulls in required fields.
- Spot-check `Event_Type` uniqueness for leftover old forms (`& Under`, `Year Olds`, `Free`, `Back`).
- Spot-check known swimmers/events in app (example: Siya Mishra + `25 Yard Butterfly`, `100 Yard IM`).

