from typing import TypedDict


class StickmanTemplate(TypedDict):
    key: str
    label: str
    positive_core: str
    negative_extra: str
    trigger_hint: str
    shot_hint: str


class StickmanReference(TypedDict):
    name: str
    kind: str
    url: str
    note: str


STICKMAN_REFERENCES: tuple[StickmanReference, ...] = (
    {
        "name": "Civitai Stickfigures SDXL LoRA",
        "kind": "lora",
        "url": "https://civitai.green/models/700803/stickfigures",
        "note": "SDXL 1.0 stick figure LoRA, trigger words include Flipchartvisu and Stick figure.",
    },
    {
        "name": "Civitai SDXL prompt phrasing guide",
        "kind": "prompting_guide",
        "url": "https://civitai.red/articles/3847/how-to-phrase-your-sdxl-prompts",
        "note": "Recommends simple ordered keyword groups over long narration-style prompts for SDXL.",
    },
    {
        "name": "Civitai prompt guide PDF",
        "kind": "prompting_guide",
        "url": "https://assets-global.website-files.com/68060174d5c5548774c431f2/680ecd155378b7b440e2529b_xudotinepebenagikife.pdf",
        "note": "Organizes prompt construction around topic, camera angle, style, focus, lighting, and refined details.",
    },
)


DEFAULT_STICKMAN_TEMPLATE: StickmanTemplate = {
    "key": "default",
    "label": "Default Poster",
    "positive_core": (
        "minimalist 2d stickman explainer poster, single hero character centered, "
        "one clear action, one oversized prop, bold outline, flat shading, "
        "instantly readable, high contrast, plain white background, simple ground line, no text"
    ),
    "negative_extra": (
        "text, logo, watermark, speech bubble, dialogue bubble, crowd, multiple characters, "
        "comic panel grid, photorealistic face, realistic landscape, detailed scenery, "
        "extra fingers, blurry, cluttered background, tiny subject, unreadable scene"
    ),
    "trigger_hint": "Stick figure",
    "shot_hint": "medium action shot, full body view",
}


STICKMAN_TEMPLATES: tuple[StickmanTemplate, ...] = (
    {
        "key": "giant_battle",
        "label": "Giant Battle",
        "positive_core": (
            "minimalist 2d stickman battle poster, single tiny hero centered, "
            "giant shadow towering ahead, oversized sling and stone, bold outline, "
            "flat shading, high contrast, empty dramatic background, no text"
        ),
        "negative_extra": "crowd, multiple heroes, detailed mountains, realistic armor, tiny weapon",
        "trigger_hint": "Stick figure",
        "shot_hint": "wide establishing shot, full body view",
    },
    {
        "key": "prayer",
        "label": "Prayer",
        "positive_core": (
            "minimalist 2d stickman prayer poster, single hero centered, "
            "kneeling on both knees, hands clasped together in front of chest, head bowed down, "
            "oversized light beam from above, bold outline, flat shading, calm high contrast, "
            "plain white background, simple ground line, no text"
        ),
        "negative_extra": (
            "standing pose, crowd, church audience, speech bubble, scenic clutter, "
            "lotus pose, yoga pose, meditation, cross legged"
        ),
        "trigger_hint": "Stick figure",
        "shot_hint": "medium wide shot, full body view",
    },
    {
        "key": "time_pressure",
        "label": "Time Pressure",
        "positive_core": (
            "minimalist 2d stickman urgency poster, single hero centered, "
            "running pose, oversized clock directly behind the hero, bold outline, "
            "flat shading, high contrast, simple background, no text"
        ),
        "negative_extra": "crowd, office workers, detailed office room, small clock, landscape",
        "trigger_hint": "Stick figure",
        "shot_hint": "medium action shot, full body view",
    },
    {
        "key": "money_choice",
        "label": "Money Choice",
        "positive_core": (
            "minimalist 2d stickman decision poster, single hero centered, "
            "holding one oversized green bill clearly in front, standing at a forked road with two large arrow signs, "
            "hesitating decision pose, bold outline, flat shading, high contrast, plain white background, "
            "simple ground line, no text"
        ),
        "negative_extra": (
            "crowd, cars, city skyline, realistic road, tiny prop, flying money, multiple bills, "
            "dancing pose, action pose"
        ),
        "trigger_hint": "Stick figure",
        "shot_hint": "wide shot, full body view",
    },
    {
        "key": "temptation",
        "label": "Temptation",
        "positive_core": (
            "minimalist 2d stickman temptation poster, single hero centered, "
            "reaching toward one glowing forbidden object, bold outline, flat shading, "
            "high contrast, dark empty background, no text"
        ),
        "negative_extra": "crowd, treasure room, detailed background, tiny object, speech bubble",
        "trigger_hint": "Stick figure",
        "shot_hint": "medium action shot, full body view",
    },
    {
        "key": "recovery",
        "label": "Recovery",
        "positive_core": (
            "minimalist 2d stickman comeback poster, single hero centered, "
            "rising from the ground with determined posture, bold outline, flat shading, "
            "high contrast spotlight, simple background, no text"
        ),
        "negative_extra": "crowd, hospital room, detailed scenery, sitting pose, tiny subject",
        "trigger_hint": "Stick figure",
        "shot_hint": "medium action shot, full body view",
    },
    {
        "key": "storm_fear",
        "label": "Storm Fear",
        "positive_core": (
            "minimalist 2d stickman storm fear poster, single tiny hero centered, "
            "fearful pose facing one oversized dark wave directly ahead, heavy rain lines, "
            "bold outline, flat shading, high contrast, plain white background, simple ground line, no text"
        ),
        "negative_extra": (
            "crowd, ship crew, detailed ocean scenery, tiny wave, photoreal water, "
            "victory pose, surfing, smiling"
        ),
        "trigger_hint": "Stick figure",
        "shot_hint": "wide shot, full body view",
    },
    {
        "key": "study_focus",
        "label": "Study Focus",
        "positive_core": (
            "minimalist 2d stickman study poster, single hero centered, "
            "studying at a desk with one oversized open book, bold outline, flat shading, "
            "high contrast, simple background, no text"
        ),
        "negative_extra": "classroom crowd, detailed furniture, realistic room, tiny book",
        "trigger_hint": "Stick figure",
        "shot_hint": "medium wide shot, full body view",
    },
    {
        "key": "machine_pipeline",
        "label": "Business Machine Pipeline",
        "positive_core": (
            "flat vector stickman business explainer diagram, round white stickman business character, "
            "navy suit and red tie, central mechanical pipeline machine with two transparent chambers, "
            "gears in one chamber, glowing network nodes in the other chamber, money flow, upward arrow, "
            "blank title plate and blank label plates, thick black outlines, muted beige background, no readable text"
        ),
        "negative_extra": (
            "readable text, fake letters, logo, watermark, photorealistic face, realistic skin, anime, "
            "3d render, clutter, dense labels, tiny diagrams, subtitle bar, youtube controls"
        ),
        "trigger_hint": "Stick figure, Flipchartvisu",
        "shot_hint": "wide 16:9 business explainer diagram shot",
    },
    {
        "key": "infrastructure_bottleneck",
        "label": "Infrastructure Bottleneck",
        "positive_core": (
            "flat vector stickman business explainer diagram, worried round white stickman businessman in navy suit "
            "and red tie, electric grid cables entering a narrow funnel bottleneck, sparks near a blue AI data center, "
            "blank label panel, thick black outlines, muted beige background, no readable text"
        ),
        "negative_extra": (
            "readable text, fake letters, logo, watermark, photorealistic city, realistic human face, anime, "
            "3d render, clutter, tiny cables, dark cinematic smoke, subtitle bar, youtube controls"
        ),
        "trigger_hint": "Stick figure, Flipchartvisu",
        "shot_hint": "wide 16:9 infrastructure bottleneck explainer shot",
    },
    {
        "key": "scale_comparison",
        "label": "Business Scale Comparison",
        "positive_core": (
            "flat vector stickman business explainer diagram, two round white stickman business characters in navy suits "
            "and red ties sitting on a balance scale, one side has small blue blocks, the other side has larger glowing "
            "blue blocks, blank label areas above both sides, thick black outlines, muted beige background, no readable text"
        ),
        "negative_extra": (
            "readable text, fake letters, logo, watermark, photorealistic people, realistic office, anime, "
            "3d render, clutter, many panels, dense chart labels, subtitle bar, youtube controls"
        ),
        "trigger_hint": "Stick figure, Flipchartvisu",
        "shot_hint": "wide 16:9 comparison scale explainer shot",
    },
)
