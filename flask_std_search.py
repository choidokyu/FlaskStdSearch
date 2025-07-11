from flask import Flask, render_template, request, jsonify
import pandas as pd
import webbrowser
import threading
import os
import re
import itertools

app = Flask(__name__)


# 전역 캐시 변수
df_std_global = None
han_eng_map_global = None


def load_data_once():
    global df_std_global, han_eng_map_global

    if df_std_global is None:
        print("[INIT] Loading 표준데이터관리.xls...")
        df_std_global = pd.read_excel("data/표준데이터관리.xls", sheet_name="Sheet1")

    if han_eng_map_global is None:
        print("[INIT] Loading han_eng_map.csv...")
        han_eng_map_global = pd.read_csv("data/han_eng_map.csv", encoding="EUC-KR", usecols=[0, 1])
        han_eng_map_global.columns = han_eng_map_global.columns.str.replace('\ufeff', '')

# 표준 데이터 엑셀 파일 로딩
#def load_standard_excel():
#    print("[LOG] Loading 표준데이터관리.xls...")
#    return pd.read_excel("data/표준데이터관리.xls", sheet_name="Sheet1")

# CamelCase/PascalCase 단어 분해 함수
def split_camel_case(word):
    return re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', word)

@app.route("/", methods=["GET", "POST"])
def index():
    load_data_once()  # ✅ 캐시된 데이터 사용 준비
    
    result = []
    result_by_term = {}
    keyword = ""
    match_type = "exact"
    
    # ✅ 먼저 기본값을 선언
    option_word = True
    option_domain = True
    option_term = True

    if request.method == "POST":
        
        option_word   = 'option_word'   in request.form
        option_domain = 'option_domain' in request.form
        option_term   = 'option_term'   in request.form
        

        # 선택된 구분 리스트 구성
        selected_types = []
        if option_word:
            selected_types.append("단어")
        if option_domain:
            selected_types.append("도메인")
        if option_term:
            selected_types.append("용어")

        print("[LOG] 선택된 구분 옵션:", selected_types)
        
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
        df_std = df_std_global.copy()            # ✅ 전역에서 복사
        
        # 선택된 구분 필터 적용
        if selected_types:
            df_std = df_std[df_std["구분"].isin(selected_types)]
            print(f"[LOG] 선택된 구분만 필터링된 데이터 수: {len(df_std)}")
            
        else:
            print("[LOG] 선택된 구분이 없어 결과 없음")
            df_std = df_std.iloc[0:0]  # 빈 DataFrame 강제 설정
            


        # 한글-영문 매핑 테이블 로딩
        print("[LOG] Loading han_eng_map.csv...")
        #han_eng_map = pd.read_csv("data/han_eng_map.csv", encoding="EUC-KR", usecols=[0, 1])
        han_eng_map = han_eng_map_global.copy()  # ✅ 전역에서 복사
        #han_eng_map.columns = han_eng_map.columns.str.replace('\ufeff', '')
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

        # 기존 코드 (순서 망가짐)
        #flat_terms = list(set(itertools.chain.from_iterable(mapped_groups)))
        # 중복 없이 순서를 유지하려면 dict.fromkeys 사용
        flat_terms = list(dict.fromkeys(itertools.chain.from_iterable(mapped_groups)))


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
            filtered = df_std[
                df_std["논리명"].astype(str).str.lower().apply(lambda x: match_logic(x, search_terms)) |
                df_std["물리명"].astype(str).str.lower().apply(lambda x: match_logic(x, search_terms))
            ]
        else:
            if match_type == "exact":
                filtered = df_std[
                    df_std["논리명"].astype(str).str.lower().apply(lambda x: any(x == c for c in combinations)) |
                    df_std["물리명"].astype(str).str.lower().apply(lambda x: any(x == c for c in combinations))
                ]
            else:
                filtered = df_std[
                    df_std["논리명"].astype(str).str.lower().apply(lambda x: all(term in x for term in flat_terms) or any(c in x for c in combinations)) |
                    df_std["물리명"].astype(str).str.lower().apply(lambda x: all(term in x for term in flat_terms) or any(c in x for c in combinations))
                ]

        print(f"[LOG] 필터링된 결과 행 수: {len(filtered)}")

        if not filtered.empty:
            print("[LOG] 논리명 기반 구분한글명 매핑 시작")
            
            # '물리명' 또는 '논리명' 기준으로 매핑 수행 — 여긴 논리명이 더 적합함
            df_map = han_eng_map.copy()
            df_map.columns = ["한글명", "영문명"]

            # '논리명'에 영문 단어가 포함되어 있는지 보고 매핑
            def map_korean(logic_name):
                logic_name_str = str(logic_name) if pd.notnull(logic_name) else ""
                logic_words = re.findall(r'\b\w+\b', logic_name_str)  # 단어 분리
                logic_words_lower = [w.lower() for w in logic_words]

                for _, row in df_map.iterrows():
                    eng = str(row["영문명"]).lower().replace(" ", "")
                    if eng in logic_words_lower:
                        print(f"[MAP] 논리명 '{logic_name}' → 단어 '{eng}' 매칭 → 한글명: '{row['한글명']}'")
                        return row["한글명"]

                print(f"[MAP] 논리명 '{logic_name}' → 매칭 없음")
                return ""



            filtered["구분한글명"] = filtered["논리명"].apply(map_korean)

            print("[LOG] 구분한글명 매핑 완료")

            filtered["sort_order"] = filtered["구분"].map(order).fillna(99)
            filtered = filtered.sort_values("sort_order").drop(columns=["sort_order"])
            
            result = filtered.to_dict(orient="records")
            
            if len(filtered) == 1:
                print("[LOG] 통합 결과가 1건이므로 각 단어별 결과도 함께 조회합니다.")

                # map_korean 함수 재정의 되어 있어야 함 (위 if와 동일)
                df_map = han_eng_map.copy()
                df_map.columns = ["한글명", "영문명"]

                def map_korean(logic_name):
                    logic_name_str = str(logic_name) if pd.notnull(logic_name) else ""
                    logic_words = re.findall(r'\b\w+\b', logic_name_str)
                    logic_words_lower = [w.lower() for w in logic_words]
                    for _, row in df_map.iterrows():
                        eng = str(row["영문명"]).lower().replace(" ", "")
                        if eng in logic_words_lower:
                            return row["한글명"]
                    return ""

                for term in flat_terms:
                    if match_type == "exact":
                        per_term = df_std[
                            (df_std["논리명"].astype(str).str.lower() == term) |
                            (df_std["물리명"].astype(str).str.lower() == term)
                        ]
                    else:
                        per_term = df_std[
                            df_std["논리명"].astype(str).str.lower().str.contains(term) |
                            df_std["물리명"].astype(str).str.lower().str.contains(term)
                        ]

                    if not per_term.empty:
                        print(f"[LOG] [1건 fallback] '{term}' → {len(per_term)}개 결과")
                        
                        # 예: per_term = per_term[조건]
                        per_term = per_term[per_term["구분"] == "단어"]

                        per_term = per_term.copy()
                        per_term["구분한글명"] = per_term["논리명"].apply(map_korean)

                        per_term["sort_order"] = per_term["구분"].map(order).fillna(99)
                        per_term = per_term.sort_values("sort_order").drop(columns=["sort_order"])

                        result_by_term[term] = per_term.to_dict(orient="records")
                        
                        print(f"[LOG] 최종 result_by_term keys: {list(result_by_term.keys())}")
            
            
            
        else:
            print("[LOG] 조합 결과 없음 → 단어별 개별 필터링 시도")
            
            # 구분한글명 매핑 함수 재사용을 위해 정의된 상태여야 함
            df_map = han_eng_map.copy()
            df_map.columns = ["한글명", "영문명"]

            def map_korean(logic_name):
                logic_name_str = str(logic_name) if pd.notnull(logic_name) else ""
                logic_words = re.findall(r'\b\w+\b', logic_name_str)
                logic_words_lower = [w.lower() for w in logic_words]
                for _, row in df_map.iterrows():
                    eng = str(row["영문명"]).lower().replace(" ", "")
                    if eng in logic_words_lower:
                        return row["한글명"]
                return ""
            
            for term in flat_terms:
                if match_type == "exact":
                    per_term = df_std[
                        (df_std["논리명"].astype(str).str.lower() == term) |
                        (df_std["물리명"].astype(str).str.lower() == term)
                    ]
                else:
                    per_term = df_std[
                        df_std["논리명"].astype(str).str.lower().str.contains(term) |
                        df_std["물리명"].astype(str).str.lower().str.contains(term)
                    ]
                    
                if not per_term.empty:
                    print(f"[LOG] '{term}' → {len(per_term)}개 결과")
                    
                    # 예: per_term = per_term[조건]
                    per_term = per_term[per_term["구분"] == "단어"]
                    
                    # ✅ 구분한글명 매핑 추가
                    per_term["구분한글명"] = per_term["논리명"].apply(map_korean)
                    
                    per_term["sort_order"] = per_term["구분"].map(order).fillna(99)
                    per_term = per_term.sort_values("sort_order").drop(columns=["sort_order"])
                    
                    result_by_term[term] = per_term.to_dict(orient="records")
                    
                    print(f"[LOG] 최종 result_by_term keys: {list(result_by_term.keys())}")
                    
                    ## ✅ 예시 row 저장
                    #if not 'example_row' in locals() and not per_term.empty:
                    #    #example_row = per_term.iloc[0]  ← 이건 Series
                    #    example_row = per_term.iloc[0].to_dict()  # ✅ dict로 변환
                    
            # ✅ 전체 단어가 포함된 논리명을 가진 행에서 예시 추출
            if 'example_row' not in locals():
                example_row = find_combined_example_row(df_std, flat_terms)


    #return render_template("index.html", result=result, result_by_term=result_by_term, keyword=keyword, match_type=match_type)
    #return render_template("index.html", result=result, result_by_term=result_by_term, keyword=keyword, match_type=match_type, example_row=locals().get('example_row'))
    return render_template(
        "index.html",
        result=result,
        result_by_term=result_by_term,
        keyword=keyword,
        match_type=match_type,
        example_row=locals().get('example_row'),
        option_word=option_word,
        option_domain=option_domain,
        option_term=option_term
    )




def find_combined_example_row(df, terms):
    """모든 단어를 포함하는 논리명 AND 구분이 '단어'인 row 추출"""
    print(f"[LOG] 예시 추출: 논리명에 모든 단어 {terms} 포함 AND 구분='단어' 인 행 검색 시작")

    for idx, row in df.iterrows():
        if str(row.get("구분", "")) != "단어":
            continue  # ✅ 구분이 '단어'가 아닌 행은 스킵

        logic_name = str(row['논리명']).lower()
        
        if all(term in logic_name for term in terms):
            print(f"[LOG] 예시 행 발견 → 논리명: '{row['논리명']}', 물리명: '{row['물리명']}' (구분: {row['구분']})")
            return row.to_dict()

    print("[LOG] 예시로 사용할 조합 논리명 행을 찾지 못함 (구분=단어 조건 포함)")
    return None





# 브라우저 자동 열기
def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")


@app.route("/update_mapping", methods=["POST"])
def update_mapping():
    data = request.get_json()
    korean = data.get("korean")
    english = data.get("english")

    print("[LOG] 클라이언트에서 받은 데이터:")
    print(f"한글명: {korean}")
    print(f"영문명: {english}")

    # CSV 파일 경로
    file_path = "data/han_eng_map.csv"

    try:
        # 파일 읽기
        df = pd.read_csv(file_path, encoding="EUC-KR")

        # 일치하는 행 찾기
        match = df["영문명"] == english
        if not match.any():
            return jsonify({"status": "fail", "message": f"'{english}'에 해당하는 항목을 찾을 수 없습니다."}), 404

        # 한글명 수정
        df.loc[match, "한글명"] = korean

        # 파일 저장
        df.to_csv(file_path, index=False, encoding="EUC-KR")
        
        # ✅ 전역 캐시 갱신
        global han_eng_map_global
        han_eng_map_global = df.copy()
        
        print("[LOG] 수정 완료 및 저장됨")
        return jsonify({
            "status": "success",
            "updated_korean": korean,
            "matched_english": english
        })

    except Exception as e:
        print("[ERROR]", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500





#if __name__ == "__main__":
#    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
#        threading.Timer(1.5, open_browser).start()
#    app.run(debug=True)


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 0))

    if port:  # Fly.io 에서 실행할 때
        app.run(host="0.0.0.0", port=port)
    else:  # 내 컴퓨터에서 실행할 때
        import webbrowser
        import threading

        def open_browser():
            webbrowser.open_new("http://127.0.0.1:5000")

        threading.Timer(1.5, open_browser).start()
        app.run(debug=True, port=5000)
