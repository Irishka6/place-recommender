import os
import sqlite3
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List

app = FastAPI()


class SearchRequest(BaseModel):
    query: str = ""
    visited: str = ""
    categories: List[str] = []
    tags: List[str] = []
    sortBy: str = "rating"


def get_db_data():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(BASE_DIR, 'data', 'database.db')

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT l.id, l.title, l.category, l.address, l.ai_summary, l.maps_url, l.rating,
               GROUP_CONCAT(t.name) as tags
        FROM Locations l
        LEFT JOIN Location_Tags lt ON l.id = lt.location_id
        LEFT JOIN Tags t ON lt.tag_id = t.id
        WHERE l.ai_summary IS NOT NULL
        GROUP BY l.id
    """)
    rows = cursor.fetchall()
    conn.close()

    places = []
    for row in rows:
        try:
            rating_val = float(row["rating"]) if row["rating"] is not None else 5.0
        except ValueError:
            rating_val = 5.0

        places.append({
            "id": row["id"],
            "title": row["title"],
            "city": "Москва",
            "category": row["category"],
            "address": row["address"],
            "desc": row["ai_summary"],
            "rating": rating_val,
            "maps_url": row["maps_url"],
            "tags": row["tags"].split(",") if row["tags"] else []
        })
    return places


def levenshtein(a: str, b: str) -> int:
    if not a: return len(b)
    if not b: return len(a)
    matrix = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1): matrix[i][0] = i
    for j in range(len(b) + 1): matrix[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            matrix[i][j] = min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1, matrix[i - 1][j - 1] + cost)
    return matrix[len(a)][len(b)]


def is_fuzzy_match(query: str, text: str) -> bool:
    if not query: return True
    if query in text: return True

    words = [text] + text.split()
    max_typos = 1 if len(query) <= 4 else 2

    for word in words:
        if len(query) > 2:
            prefix = word[:len(query)]
            if levenshtein(query, prefix) <= max_typos:
                return True
    return False


@app.post("/api/search")
def search_places(req: SearchRequest):
    places = get_db_data()

    query = req.query.strip().lower()
    visited_list = [v.strip().lower() for v in req.visited.split(',') if v.strip()]

    search_triggered_tags = set()
    exact_match_ids = set()

    # Поиск опечаток работает сразу здесь (для выдачи карточек)
    if query:
        for item in places:
            if is_fuzzy_match(query, item["title"].lower()):
                exact_match_ids.add(item["id"])
                if item["tags"]:
                    search_triggered_tags.update(item["tags"])

    scored_items = []
    for item in places:
        score = 0
        match_type = 'none'
        shared_tags_count = 0

        if item["id"] in exact_match_ids:
            score = 1000
            match_type = 'exact'
        elif query:
            if item["tags"]:
                for t in item["tags"]:
                    if t in search_triggered_tags:
                        shared_tags_count += 1

            if shared_tags_count > 0:
                score = shared_tags_count * 10
                match_type = 'similar'
            elif (item.get("city") and is_fuzzy_match(query, item["city"].lower())) or is_fuzzy_match(query, item[
                "title"].lower()):
                score = 50
                match_type = 'exact'
        else:
            score = 50
            match_type = 'regular'

        # Фильтры
        if any(is_fuzzy_match(v, item["title"].lower()) for v in visited_list):
            score = 0
        if req.categories and item["category"] not in req.categories:
            score = 0
        if req.tags:
            if not item["tags"] or not any(t in item["tags"] for t in req.tags):
                score = 0

        if score > 0:
            item["score"] = score
            item["matchType"] = match_type
            item["sharedTagsCount"] = shared_tags_count
            scored_items.append(item)

    if req.sortBy == 'rating':
        scored_items.sort(key=lambda x: x.get("rating", 5.0), reverse=True)
    elif req.sortBy == 'name':
        scored_items.sort(key=lambda x: x["title"])

    scored_items.sort(key=lambda x: x["score"], reverse=True)
    return scored_items


@app.get("/api/tags")
def get_tags():
    places = get_db_data()
    tags_set = set()
    for p in places:
        for t in p.get("tags", []):
            tags_set.add(t)
    return sorted(list(tags_set))


app.mount("/", StaticFiles(directory="static", html=True), name="static")