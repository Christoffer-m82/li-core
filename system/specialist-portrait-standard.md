# Specialist portrait standard

Owner-directed baseline for all future specialist thumbnail portraits, including additions and
requested revisions. This is a visual design specification, not an agent identity, capability,
qualification, or permission change. The [Li Constitution](../CONSTITUTION.md),
[security policy](security-policy.md), and [update policy](update-policy.md) remain authoritative.

## Scope and source of truth

Use each specialist's existing **Name** and full **Role** from
[the agent registry](../agents/registry.yaml), selecting entries with `type: specialist`.
Do not invent or rename agents for a portrait request. Primary and system agents are separate;
include them only when requested. Creating artwork does not authorize creating a permanent agent.

Before designing any portrait, read the entire
[portrait assignment record](specialist-portrait-assignments.md) and compare it with the current
registry. Maintain one roster-wide design plan; do not make isolated choices without checking
existing portraits. For a new specialist, retain existing approved portraits and choose a distinct
new combination. Generating the whole existing roster again is not required for an addition.

## Per-specialist rules

1. The portrait's gender must match the gender typically associated with the first name. For a
   gender-ambiguous or unisex name, choose either male or female to help balance the overall roster.
   This is fictional character casting, not a rule for inferring a real person's gender.
2. Choose an appropriate age, ethnicity/background, hair and styling that fit the fictional
   character. Names and roles do not determine ethnicity; do not stereotype role-to-demographic
   choices or repeat a default look for finance, nutrition, or any other category.
3. Clothing must realistically fit the specific workplace: clinical scrubs or a white coat for
   medical; athletic clothing for fitness; a tailored suit for legal; a chef's jacket for cooking;
   a smart-casual sweater for coaching/advice. Do not dress every specialist in a generic blazer.
4. Keep styling polished, neutral and professional in that context, with well-groomed hair and
   conventional clothing. Avoid the owner's excluded visual treatments: dreadlocks, tie-dye,
   focal-point piercings/tattoos, protest-style clothing, and countercultural or bohemian styling.
   These are aesthetic constraints only, not judgments about people or inferred political beliefs.
5. Match expression and demeanor to the role: reassuring for medical, energetic for fitness,
   warm for relationships, sharp and composed for legal, and similarly appropriate for other roles.
6. Assign a plain solid background colour suited to the role/category and distinct from every
   existing background. Record both a descriptive colour name and its target hex value.

## Whole-roster variety rules

- Mix late 20s, 30s, 40s and 50s across the roster.
- Vary ethnicity/background; do not repeat a demographic pattern by role.
- Vary hair colour, length, style and facial hair so no two specialists look alike.
- Do not assign the same or a visually similar background colour to two specialists. Different
  hex values alone do not establish perceptual difference; inspect the images together.
- Track age range, fictional ethnicity/background, gender, hair/facial hair, clothing, expression
  and background before generation. Deliberately avoid repeated combinations.
- For a whole-roster request, prepare all assignments and prompts in one coordinated pass.
  Individual image-generation calls may follow that shared plan; do not re-randomize each portrait
  independently or lose the roster-wide assignment record between calls.

## Required prompt output

List the specialist's exact **Name and Role** above each prompt. Use this template, substituting
the planned values and making only necessary grammatical agreement changes (for example, her/his
and a/an). Do not replace it with a generic portrait description.

```text
Professional photorealistic headshot portrait, [ethnicity] [gender] in their [age range] with
[hair description], wearing [clothing appropriate to their specific role/workplace], looking
directly at camera with a [role-appropriate expression], soft natural studio lighting, shallow
depth of field, shoulders-up crop, plain solid [unique background color] background, high
resolution, shot on 85mm lens, realistic skin texture, no text, no logo, not a real
identifiable person
```

Use square, centred framing with sufficient headroom for the whole hairstyle and a consistent
face scale across the collection. Preserve natural skin detail rather than plastic retouching.
The portraits are fictional representations of AI specialists, not photographs of real staff.

## Generation, revisions and handoff

1. Check the registry and assignment record before proposing or generating a new portrait.
2. Record the complete proposed assignment and exact prompt; compare the full set for collisions.
3. Generate with the available image-generation workflow. Inspect face, expression, clothing,
   crop, background, artifacts, and distinctiveness against the roster at thumbnail size.
4. Save the original-resolution image. Record actual pixel dimensions rather than assuming a
   generator's output size. Make smaller web derivatives separately if implementation needs them.
5. Preserve originals unless the owner explicitly requests removal. Keep revision identifiers
   internal to the asset workflow, never in specialist names or user-facing labels. Promote the
   selected portrait to its canonical agent-key filename and never distribute superseded artwork.
6. Include the selected image, prompt, version, dimensions, and approval/selection status in the
   handoff. Preview generation is not automatic approval to integrate, commit or deploy images.
7. Preserve names and roles as readable UI labels; do not make portrait colour or perceived
   appearance the only way to identify a specialist. Theme changes should not silently recolour
   portraits or change their identities.

Elena is always named **Elena**, without revision labels. Her selected portrait has auburn hair,
a chef's jacket and a yellow background. The owner requested removal of the previous portrait.
