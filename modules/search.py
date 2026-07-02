"""
Social graph BFS search — async face search through Instagram network.
"""
import json, os, sys, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import config
from modules.instagram import Instagram
from modules.face import FaceEngine

class BFSSearch:
    def __init__(self, ref_image_path, cookie_string=None, workers=None, face_engine=None, ref_emb=None):
        self.ref_path = ref_image_path
        self.cookie = cookie_string or config.COOKIE_STRING
        self.workers = workers or config.WORKERS
        if face_engine:
            self.face = face_engine
            self.ref_emb = ref_emb
        else:
            self.face = FaceEngine(config.MODEL_NAME)
            self.ref_emb = self.face.get_embedding_from_path(ref_image_path)
        if self.ref_emb is None:
            raise ValueError(f"No face detected in reference image: {ref_image_path}")
        self.checked_users = set()
        self.checked_urls = set()
        self.expanded_users = set()
        self.results = []
        self.found = asyncio.Event()
        self.found_data = [None]
        self.lock = asyncio.Lock()
        self.total_face_checks = 0

    async def _check_one(self, username):
        if self.found.is_set(): return None
        async with self.lock:
            if username in self.checked_users: return None
            self.checked_users.add(username)

        try:
            async with Instagram(self.cookie, timeout=config.PLAYWRIGHT_TIMEOUT, skip_home=True) as ig:
                url, pic = await ig.get_profile_pic(username)
                if not pic: return None

                async with self.lock:
                    if url in self.checked_urls: return None
                    self.checked_urls.add(url)

                sim = self.face.compare_to_ref(pic, self.ref_emb)
                if sim is not None:
                    async with self.lock:
                        self.results.append((username, sim))
                        self.total_face_checks += 1
                    if sim >= config.SIM_THRESHOLD:
                        self.found.set()
                        self.found_data[0] = (username, sim)
                        return (username, sim)
        except Exception as e:
            print(f"  _check_one error @{username}: {e}", flush=True)
        return None

    async def search(self, usernames, depth=1, batch_label=""):
        if self.found.is_set() or not usernames:
            return []

        label = batch_label or f"depth {depth}"
        print(f"\n  [{label}] Checking {len(usernames)} accounts...", flush=True)

        # --- Phase 1: check all faces (parallel) ---
        expand_candidates = []
        sem = asyncio.Semaphore(self.workers)

        async def _check_with_sem(u):
            async with sem:
                return u, await self._check_one(u)

        tasks = {asyncio.ensure_future(_check_with_sem(u)): u for u in usernames}
        pending = set(tasks.keys())
        done_count = 0

        while pending and not self.found.is_set():
            done_set, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for t in done_set:
                done_count += 1
                username = tasks[t]
                if done_count % 10 == 0:
                    print(f"    [{done_count}/{len(usernames)}] {username}", flush=True)
                try:
                    _, result = t.result()
                except Exception:
                    result = None
                if result is None:
                    expand_candidates.append(username)

        for t in pending:
            t.cancel()

        if self.found.is_set():
            return []

        # --- Phase 2: expand to next layer ---
        if depth <= 1 or not expand_candidates:
            return sorted(self.results, key=lambda x: -x[1])

        expand = [u for u in expand_candidates if u not in self.expanded_users]
        if not expand:
            return sorted(self.results, key=lambda x: -x[1])

        print(f"\n  [{label}] Expanding {len(expand)} accounts ke depth {depth-1}...", flush=True)

        for i, uname in enumerate(expand):
            if self.found.is_set():
                break
            async with self.lock:
                self.expanded_users.add(uname)

            print(f"    [{i+1}/{len(expand)}] @{uname} fetching friends...", flush=True)

            try:
                async with Instagram(self.cookie, timeout=config.PLAYWRIGHT_TIMEOUT, skip_home=True) as ig:
                    followers = await ig.get_followers(uname)
                    following = await ig.get_following(uname)
            except Exception as e:
                print(f"      Error fetching @{uname}: {e}", flush=True)
                continue

            if followers:
                sub = [u for u in followers if u not in self.checked_users]
                if sub:
                    print(f"      followers: {len(followers)} -> {len(sub)} baru", flush=True)
                    await self.search(sub, depth - 1, f"{uname}/f")
                    if self.found.is_set():
                        return []

            if following:
                sub = [u for u in following if u not in self.checked_users]
                if sub:
                    print(f"      following: {len(following)} -> {len(sub)} baru", flush=True)
                    await self.search(sub, depth - 1, f"{uname}/g")
                    if self.found.is_set():
                        return []

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
