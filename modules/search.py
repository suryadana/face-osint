"""
Social graph BFS search — recursive face search through Instagram network.
"""
import json, time, threading, queue, os, sys
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path: sys.path.insert(0, BASE)

from modules import config
from modules.instagram import Instagram
from modules.face import FaceEngine

class BFSSearch:
    def __init__(self, ref_image_path, cookie_string=None, workers=None):
        self.ref_path = ref_image_path
        self.cookie = cookie_string or config.COOKIE_STRING
        self.workers = workers or config.WORKERS
        self.face = FaceEngine(config.MODEL_NAME)
        self.ref_emb = self.face.get_embedding_from_path(ref_image_path)
        if self.ref_emb is None:
            raise ValueError(f"No face detected in reference image: {ref_image_path}")
        self.checked_users = set()
        self.checked_urls = set()
        self.expanded_users = set()
        self.results = []
        self.found = threading.Event()
        self.found_data = [None]
        self.lock = threading.Lock()
        self.total_face_checks = 0

    def _check_one(self, username):
        """Check a single user's profile pic against reference. Thread-safe."""
        if self.found.is_set(): return None
        with self.lock:
            if username in self.checked_users: return None
            self.checked_users.add(username)

        try:
            ig = Instagram(self.cookie, timeout=config.PLAYWRIGHT_TIMEOUT)
        except Exception as e:
            return None
        try:
            url, pic = ig.get_profile_pic(username)
            if not pic: return None

            with self.lock:
                if url in self.checked_urls: return None
                self.checked_urls.add(url)

            sim = self.face.compare_to_ref(pic, self.ref_emb)
            if sim is not None:
                with self.lock:
                    self.results.append((username, sim))
                    self.total_face_checks += 1
                if sim >= config.SIM_THRESHOLD:
                    self.found.set()
                    self.found_data[0] = (username, sim)
                    return (username, sim)
        finally:
            try: ig.close()
            except: pass
        return None

    def search(self, usernames, depth=1, batch_label=""):
        """
        Recursive BFS face search.
        Hanya skip user yang sudah pernah di-check. Tidak ada batasan jumlah expand.

        Args:
            usernames: list of Instagram usernames to check
            depth: remaining depth to expand (0 = no expansion)
            batch_label: label for logging
        """
        if self.found.is_set() or not usernames:
            return []
        
        label = batch_label or f"depth {depth}"
        print(f"\n  [{label}] Checking {len(usernames)} accounts...", flush=True)

        # --- PHASE 1: Check all faces in this layer (parallel) ---
        expand_candidates = []
        pool = ThreadPoolExecutor(max_workers=self.workers)
        futures = {pool.submit(self._check_one, u): u for u in usernames}
        done_count = 0

        for f in as_completed(futures):
            if self.found.is_set():
                for ff in futures: ff.cancel()
                break
            done_count += 1
            username = futures[f]
            if done_count % 10 == 0:
                print(f"    [{done_count}/{len(usernames)}] {username}", flush=True)
            result = f.result()
            if result is None and username not in expand_candidates:
                expand_candidates.append(username)

        pool.shutdown()

        if self.found.is_set():
            return []

        # --- PHASE 2: Expand to next layer (if depth remains) ---
        if depth <= 1 or not expand_candidates:
            return sorted(self.results, key=lambda x: -x[1])

        expand = [u for u in expand_candidates if u not in self.expanded_users]
        if not expand:
            return sorted(self.results, key=lambda x: -x[1])

        print(f"\n  [{label}] Expanding {len(expand)} accounts ke depth {depth-1}...", flush=True)

        for i, uname in enumerate(expand):
            if self.found.is_set():
                break
            with self.lock:
                self.expanded_users.add(uname)

            print(f"    [{i+1}/{len(expand)}] @{uname} fetching friends...", flush=True)

            ig = Instagram(self.cookie, timeout=config.PLAYWRIGHT_TIMEOUT)
            try:
                followers = ig.get_followers(uname)
                if followers:
                    sub = [u for u in followers if u not in self.checked_users]
                    if sub:
                        print(f"      followers: {len(followers)} -> {len(sub)} baru", flush=True)
                        self.search(sub, depth - 1, f"{uname}/f")
                        if self.found.is_set():
                            return []

                following = ig.get_following(uname)
                if following:
                    sub = [u for u in following if u not in self.checked_users]
                    if sub:
                        print(f"      following: {len(following)} -> {len(sub)} baru", flush=True)
                        self.search(sub, depth - 1, f"{uname}/g")
                        if self.found.is_set():
                            return []
            finally:
                ig.close()

        return sorted(self.results, key=lambda x: -x[1])

    def get_top(self, n=20):
        return sorted(self.results, key=lambda x: -x[1])[:n]

    def save_results(self, path=None):
        if not path:
            path = os.path.join(config.RESULTS_DIR, "face_search_result.json")
        top = self.get_top(50)
        data = {
            "found": self.found_data[0] is not None,
            "match": {"username": self.found_data[0][0], "similarity": self.found_data[0][1]} if self.found_data[0] else None,
            "threshold": config.SIM_THRESHOLD,
            "total_checked": len(self.checked_users),
            "total_faces": len(self.results),
            "total_face_checks": self.total_face_checks,
            "top_50": [{"username": u, "similarity": round(s*100, 2)} for u, s in top]
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path

    def load_results(self, path):
        with open(path) as f:
            return json.load(f)
