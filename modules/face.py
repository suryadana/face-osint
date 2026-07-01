"""
Face comparison engine — insightface buffalo_l
"""
import cv2, insightface, numpy as np
from numpy.linalg import norm

class FaceEngine:
    def __init__(self, model_name="buffalo_l"):
        self.model = insightface.app.FaceAnalysis(name=model_name)
        self.model.prepare(ctx_id=0)

    def get_embedding(self, img_data):
        """Extract face embedding from raw image bytes. Returns embedding or None."""
        img = cv2.imdecode(np.frombuffer(img_data, np.uint8), cv2.IMREAD_COLOR)
        if img is None: return None
        faces = self.model.get(img)
        if len(faces) == 0: return None
        return faces[0].embedding

    def get_embedding_from_path(self, path):
        """Extract face embedding from image file path."""
        img = cv2.imread(path)
        if img is None: return None
        faces = self.model.get(img)
        if len(faces) == 0: return None
        return faces[0].embedding

    def compare(self, emb1, emb2):
        """Cosine similarity between two embeddings. Returns float 0-1."""
        return float(emb1 @ emb2 / (norm(emb1) * norm(emb2)))

    def compare_images(self, img_data1, img_data2):
        """Compare two face images (raw bytes). Returns (sim, emb1, emb2) or (None, None, None)."""
        emb1 = self.get_embedding(img_data1)
        emb2 = self.get_embedding(img_data2)
        if emb1 is None or emb2 is None: return None, None, None
        return self.compare(emb1, emb2), emb1, emb2

    def compare_to_ref(self, img_data, ref_emb):
        """Compare image bytes to a reference embedding."""
        emb = self.get_embedding(img_data)
        if emb is None: return None
        return self.compare(ref_emb, emb)

    def batch_compare(self, img_datas, ref_emb):
        """Compare multiple images to reference embedding. Returns list of (index, sim) or None."""
        results = []
        for i, data in enumerate(img_datas):
            emb = self.get_embedding(data)
            if emb is not None:
                results.append((i, self.compare(ref_emb, emb)))
        return results
