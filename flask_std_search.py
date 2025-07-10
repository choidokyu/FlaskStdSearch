from flask import Flask, render_template, request
import pandas as pd
import webbrowser
import threading
import os
import re
import itertools

app = Flask(__name__)

# 표준 데이터 엑셀 파일 로딩
def load_standard_excel():
    print("[LOG] Loading 표준데이터관리.xls...")
    return pd.read_excel("data/표준데이터관리.xls", sheet_name="Sheet1")

# CamelCase/PascalCase 단어 분해 함수
def split_camel_case(word):
    return re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', word)

@app.route("/", methods=["GET", "POST"])
def index():
    result = []
    result_by_term = {}
    keyword = ""
    match_type = "exact"

    if request.method == "POST":
        keyword = request.form["keyword"].strip()
        match_type = request.form.get("match_type", "exact")
        print(f"[LOG] 사용자 입력 키워드: {keyword}")
        print(f"[LOG] 선택된 매칭 방식: {match_type}")

        # 키워드 분해 처리
        raw_terms = keyword.split()
        expanded_terms = []

        for term in raw_terms:
            if re.fullmatch(r"[A-Za-z]+", term):
                split_terms = split_camel_case(term)
                print(f"[LOG] '{term}' → 분해된 단어들: {split_terms}")
                expanded_terms.extend(split_terms)
            else:
                expanded_terms.append(term)

        terms = [t for t in expanded_terms if t]
        print(f"[LOG] 최종 분리된 검색어 terms: {terms}")

        # 표준 데이터 로딩
        df_std = load_standard_excel()

        # 한글-영문 매핑 테이블 로딩
        print("[LOG] Loading han_eng_map.csv...")
        han_eng_map = pd.read_csv("data/han_eng_map.csv", encoding="EUC-KR", usecols=[0, 1])
        han_eng_map.columns = han_eng_map.columns.str.replace('\ufeff', '')
        print("[LOG] 매핑 테이블 컬럼명:", han_eng_map.columns.tolist())

        # 단어 매핑
        mapped_groups = []
        for term in terms:
            if re.fullmatch(r"[A-Za-z0-9_]+", term):
                print(f"[LOG] 영문 직접 입력: {term}")
                mapped_groups.append([term.lower()])
            else:
                mapped = han_eng_map[han_eng_map["한글명"].str.contains(term, na=False)]["영문명"].tolist()
                if mapped:
                    print(f"[LOG] 한글 '{term}' → 매핑된 영문: {mapped}")
                    mapped_groups.append([m.lower().replace(" ", "") for m in mapped])
                else:
                    print(f"[LOG] 한글 '{term}' → 매핑 없음, 원래 단어 사용")
                    mapped_groups.append([term.lower()])

        flat_terms = list(set(itertools.chain.from_iterable(mapped_groups)))

        combinations = []
        if len(mapped_groups) >= 2:
            combinations = [''.join(p) for p in itertools.product(*mapped_groups)]
            print(f"[LOG] 조합된 단어들 추가: {combinations}")

        search_terms = flat_terms + combinations
        print(f"[LOG] 최종 검색 대상 영문 terms: {search_terms}")

        # 정렬 기준
        order = {"단어": 0, "도메인": 1, "용어": 2}

        # 필터 함수
        def match_logic(x, terms):
            if match_type == "exact":
                return any(x == term for term in terms)
            else:
                return any(term in x for term in terms)

        # 통합 검색
        filtered = pd.DataFrame()
        if len(terms) == 1:
            filtered = df_std[df_std["논리명"].astype(str).str.lower().apply(
                lambda x: match_logic(x, search_terms)
            )]
        else:
            if match_type == "exact":
                filtered = df_std[df_std["논리명"].astype(str).str.lower().apply(
                    lambda x: any(x == c for c in combinations)
                )]
            else:
                filtered = df_std[df_std["논리명"].astype(str).str.lower().apply(
                    lambda x: all(term in x for term in flat_terms) or any(c in x for c in combinations)
                )]

        print(f"[LOG] 필터링된 결과 행 수: {len(filtered)}")

        if not filtered.empty:
            filtered["sort_order"] = filtered["구분"].map(order).fillna(99)
            filtered = filtered.sort_values("sort_order").drop(columns=["sort_order"])
            result = filtered.to_dict(orient="records")
        else:
            print("[LOG] 조합 결과 없음 → 단어별 개별 필터링 시도")
            for term in flat_terms:
                if match_type == "exact":
                    per_term = df_std[df_std["논리명"].astype(str).str.lower() == term]
                else:
                    per_term = df_std[df_std["논리명"].astype(str).str.lower().str.contains(term)]
                if not per_term.empty:
                    print(f"[LOG] '{term}' → {len(per_term)}개 결과")
                    per_term["sort_order"] = per_term["구분"].map(order).fillna(99)
                    per_term = per_term.sort_values("sort_order").drop(columns=["sort_order"])
                    result_by_term[term] = per_term.to_dict(orient="records")

    return render_template("index.html", result=result, result_by_term=result_by_term, keyword=keyword, match_type=match_type)

# 브라우저 자동 열기
def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Timer(1.5, open_browser).start()
    app.run(debug=True)
