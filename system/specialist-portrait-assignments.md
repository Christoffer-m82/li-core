# Specialist portrait assignments

Design ledger for applying the [portrait standard](specialist-portrait-standard.md).
Names and roles below match [the specialist registry](../agents/registry.yaml).
Appearance descriptions are fictional casting specifications, not verified ancestry or personal
facts about real people. Colours are generation targets; rendered pixels can vary with lighting.

## Current collection

The owner selected the collection and requested integration into the specialist interface.
Elena uses the approved auburn-haired portrait and is always called Elena. This does not
establish approval for production deployment. All current originals are 1254 × 1254 PNGs.

| Name | Exact role | Gender / age | Fictional background | Hair / facial hair | Background target |
| --- | --- | --- | --- | --- | --- |
| Sofia | Health & Medical Adviser | Female, early 40s | Greek | Dark-brown low chignon | Muted teal `#257D82` |
| Marco | Fitness & Performance Coach | Male, early 30s | Afro-Brazilian | Short tight black curls, tapered cut; clean-shaven | Burnt orange `#D96A24` |
| Elena | Nutrition, Cooking, Food & Drink Expert | Female, mid-30s | Portuguese | Auburn hair in a bun; soft freckles, hazel eyes | Butter yellow `#F2D76B` |
| Amelia | Relationships, Dating & Social Adviser | Female, early 40s | British Indian | Long espresso-brown waves, pinned on one side | Dusty rose `#BE7188` |
| Freja | Parenting & Family Adviser | Female, early 50s | Danish | Ash-blonde pixie with silver at temples | Powder blue `#B7D6F2` |
| Oliver | Legal & Regulatory Adviser | Male, early 50s | Black British, Ghanaian heritage | Closely shaved head; trimmed salt-and-pepper beard | Midnight navy `#172C50` |
| James | Finance & Wealth Adviser | Male, mid-40s | British Chinese | Straight black side-part; clean-shaven | Deep forest green `#244E39` |
| Victor | Business, Commercial & CCO Adviser | Male, late 50s | Colombian Latino | Swept-back silver hair; trimmed silver moustache | Dark aubergine `#512944` |
| Nora | Research, Intelligence & Decision Adviser | Female, late 20s | Lebanese | Straight chestnut high ponytail | Pale lavender `#D1C2EC` |
| Milo | Travel, Leisure & Experiences Adviser | Male, late 20s | Mixed Japanese and Italian | Medium dark-brown brushed-back layers; light stubble | Warm sand `#D9BD94` |
| Iris | Home, Interior Design, Plants & Gardening Adviser | Female, mid-30s | Mixed Dutch and Surinamese | Short copper-brown curls in rounded crop | Brick red `#A73D35` |
| Clara | Wellbeing, Habits & Mental Performance Adviser | Female, late 40s | Argentine, European heritage | Honey-blonde shoulder-length cut, side fringe | Neutral stone grey `#A6AAA5` |

| Name | Workplace clothing | Expression |
| --- | --- | --- |
| Sofia | White clinical coat over pale-blue scrubs | Calm and reassuring |
| Marco | Fitted charcoal technical training shirt | Energetic and encouraging |
| Elena | Ivory double-breasted chef's jacket with stand collar | Warm, confident, welcoming smile |
| Amelia | Oatmeal cashmere sweater, modest rounded neckline | Warm, empathetic and attentive |
| Freja | Navy fine-gauge cardigan over cream cotton blouse | Patient, approachable and reassuring |
| Oliver | Medium-grey tailored wool suit, white shirt, burgundy tie | Sharp, composed and attentive |
| James | Navy tailored waistcoat, pale-blue shirt, dark-grey tie | Steady, thoughtful and trustworthy |
| Victor | Dark-brown executive suit, open-collar white shirt | Assured, perceptive and decisive |
| Nora | Charcoal fine-knit sweater over white Oxford shirt | Inquisitive, focused and thoughtfully sceptical |
| Milo | Slate-blue travel overshirt over white T-shirt | Friendly, curious and adventurous |
| Iris | Olive studio apron over cream work shirt | Observant, creative and warmly practical |
| Clara | Muted-plum merino top, modest boat neckline | Grounded, encouraging and optimistic |

## Current files

Application assets: `frontend/static/assets/portraits/<agent-key>.png`.
Local full-resolution collection: `output/portraits/specialists-v1/`, with each agent key plus
`.png`. Elena is `elena.png` in both locations and in the supplied ZIP. Prompts are recorded in
`PORTRAITS.md`; Elena's current prompt is also in `elena-prompt.md`.
The old Elena portrait was removed from the current collection at the owner's request.
File presence does not establish a live deployment.

## Selected system agents

The owner selected Ada, Theo and Heimdall for the combined 15-portrait collection.
Li is excluded. Earlier system-agent alternatives were removed from the active collection.
The 12 original specialists and selected Elena remain unchanged.

| Name | Exact role | Fictional appearance | Clothing | Background |
| --- | --- | --- | --- | --- |
| Ada | AI Architect & System Evolution Manager | Iranian woman, mid-60s; dark shoulder-length waves with silver strands | Ivory silk blouse and charcoal collarless jacket | Cobalt blue `#3659DB` |
| Theo | Personal Memory & Knowledge Curator | Italian man, mid-60s; bald crown, silver side hair, short white beard, no glasses | Burgundy cardigan and ivory band-collar shirt | Olive `#85842A` |
| Heimdall | Security & Privacy Guardian | German man, late 60s; wavy white hair, clean-shaven, dark rectangular glasses | Slate-blue knit polo and charcoal technical vest | Charcoal `#28282C` |

Selected originals: `output/portraits/specialists-v1/ada.png`, `theo.png`, and `heimdall.png`.
Each is 1254 × 1254 PNG. The combined `output/portraits/li-specialist-thumbnails.zip` contains
all 15 selected PNGs under canonical names, no rejected options and no Li image.
See [selected system-agent prompts](../output/portraits/specialists-v1/SYSTEM_AGENTS.md).
The local frontend contains all 15 selected assets. System agents have separate read-only cards
and profiles with the shared full-portrait viewer; they remain outside specialist analytics.
This is repository implementation, not evidence of a live deployment.

## Adding an agent portrait

Read every current assignment before choosing new traits. Record exact registry name and role,
appearance, clothing, expression, background, prompt, original dimensions and selection status.
Compare new images with the current collection. Do not regenerate approved agents to make room
for another portrait. Keep canonical names in the selected collection and distribute only keepers.
Creating or selecting an image is not evidence of deployment or a change to agent authority.
