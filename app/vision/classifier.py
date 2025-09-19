from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


@dataclass
class Classified:
    category: str      # EV | PHEV | indeterminado
    score: float
    brand: Optional[str]
    model: Optional[str]


class ZeroShotClassifier:
    """
    Zero-shot classifier using OpenCLIP (if available). If not available,
    returns 'indeterminado'.
    """

    def __init__(self):
        self.model = None
        self.preprocess = None
        self.tokenizer = None
        self.txt_prompts = []
        self.txt_meta = []
        self.cat_prompts = [
            "a photo of an electric vehicle",
            "a photo of a plug-in hybrid vehicle",
        ]
        self.txt_embeds = None
        self.cat_embeds = None
        self._try_load()

    def _try_load(self):
        try:
            import open_clip
            import torch
            arch = os.getenv("OPENCLIP_MODEL", "ViT-B-32")
            pretrained = os.getenv("OPENCLIP_PRETRAINED", "laion2b_s34b_b79k")
            local = os.getenv("OPENCLIP_WEIGHTS", "").strip()
            if local and os.path.exists(local):
                model, _, preprocess = open_clip.create_model_and_transforms(arch, pretrained=local)
            else:
                model, _, preprocess = open_clip.create_model_and_transforms(arch, pretrained=pretrained)
            model.eval()
            tok = open_clip.get_tokenizer(arch)
            self.model, self.preprocess, self.tokenizer = model, preprocess, tok
            # Wide list of brands/models can be supplied via env JSON or defaults
            default_list = [
                ("Tesla", "Model 3"), ("Tesla", "Model Y"), ("Kia", "EV6"), ("BMW", "330e"),
                ("BYD", "Dolphin"), ("Hyundai", "Ioniq 5"), ("Renault", "Megane E-Tech"),
            ]
            prompts = os.getenv("CAR_PROMPTS_JSON", "")
            import json
            pairs = json.loads(prompts) if prompts else default_list
            self.txt_prompts = [f"a photo of a {b} {m}" for (b, m) in pairs]
            self.txt_meta = pairs
            with torch.no_grad():
                t = self.tokenizer(self.txt_prompts)
                self.txt_embeds = self.model.encode_text(t).float()
                self.txt_embeds /= self.txt_embeds.norm(dim=-1, keepdim=True) + 1e-9
                t2 = self.tokenizer(self.cat_prompts)
                self.cat_embeds = self.model.encode_text(t2).float()
                self.cat_embeds /= self.cat_embeds.norm(dim=-1, keepdim=True) + 1e-9
        except Exception:
            self.model = None

    def classify(self, crop_bgr: np.ndarray) -> Classified:
        if self.model is None:
            return Classified("indeterminado", 0.0, None, None)
        import torch
        from PIL import Image
        rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        x = self.preprocess(img).unsqueeze(0)
        with torch.no_grad():
            emb = self.model.encode_image(x).float()
            emb /= emb.norm(dim=-1, keepdim=True) + 1e-9
            sim_models = (emb @ self.txt_embeds.T).cpu().numpy()[0]
            sim_cat = (emb @ self.cat_embeds.T).cpu().numpy()[0]
        mi = int(np.argmax(sim_models))
        ci = int(np.argmax(sim_cat))  # 0 EV, 1 PHEV
        brand, model = self.txt_meta[mi]
        category = "EV" if ci == 0 else "PHEV"
        score = float(0.6*sim_models[mi] + 0.4*sim_cat[ci])
        return Classified(category, round(score, 4), brand, model)


classifier = ZeroShotClassifier()

