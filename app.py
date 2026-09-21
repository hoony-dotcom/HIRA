import streamlit as st
import pandas as pd
import glob
import re
import os
import altair as alt

# 페이지 설정
st.set_page_config(
    page_title="의료장비 상세 현황 조회 시스템",
    page_icon="🏥",
    layout="wide"
)

# 1. 동일 폴더 내에서 가장 최신의 날짜(8자리: YYYYMMDD)를 가진 .xlsb 파일 자동 감지
@st.cache_data
def get_latest_file():
    pattern = "건강보험심사평가원_의료장비 상세 현황_*.xlsb"
    files = glob.glob(pattern)
    
    if not files:
        return None, None
    
    file_dates = []
    for f in files:
        match = re.search(r'_(\d{8})\.xlsb$', f)
        if match:
            file_dates.append((match.group(1), f))
            
    if not file_dates:
        latest_file = max(files, key=os.path.getmtime)
        return latest_file, "날짜 추출 불가 (최근 수정일 기준)"
    
    file_dates.sort(reverse=True)
    latest_date, latest_file = file_dates[0]
    
    formatted_date = f"{latest_date[:4]}년 {latest_date[4:6]}월 {latest_date[6:]}일"
    return latest_file, formatted_date

FILE_PATH, 기준일자 = get_latest_file()

@st.cache_data
def load_data(file_path):
    try:
        # xlsb 바이너리 파일 읽기를 위해 engine='pyxlsb' 지정
        df = pd.read_excel(file_path, engine='pyxlsb')
        df['대분류표시'] = df['장비대분류코드'].astype(str) + " - " + df['장비대분류명'].astype(str)
        df['세분류표시'] = df['장비세분류코드'].astype(str) + " - " + df['장비세분류명'].astype(str)
        return df
    except Exception as e:
        st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")
        return None

if FILE_PATH is None:
    st.error("⚠️ '건강보험심사평가원_의료장비 상세 현황_YYYYMMDD.xlsb' 형식의 파일을 찾을 수 없습니다.")
else:
    df = load_data(FILE_PATH)

    if df is not None:
        st.title("🏥 건강보험심사평가원 의료장비 상세 현황 조회 시스템")
        
        if 기준일자:
            st.info(f"📅 **데이터 기준일자:** {기준일자} (파일명: `{os.path.basename(FILE_PATH)}`)")

        # ================= 사이드바 구성 (접이식 메뉴 적용) =================
        with st.sidebar:
            # 1. 의용공학팀 개발앱 바로가기
            with st.expander("📌 의용공학팀 개발앱 바로가기", expanded=False):
                st.markdown("- [1. 의료장비 투자집행 계획 실적](https://buly.kr/DEbvdwF)")
                st.markdown("- [2. 의료장비 현황 바로가기](https://buly.kr/7mERs3u)")
                st.markdown("- [3. 건강보험심사평가원 의료장비 상세현황 조회](https://buly.kr/7mERs3u)")

            # 2. 제작 및 문의 정보
            with st.expander("🛠️ 제작 및 문의 정보", expanded=False):
                st.markdown(
                    "**인하대병원 의용공학팀**<br>"
                    "[dhkoh@inhauh.com](mailto:dhkoh@inhauh.com)",
                    unsafe_allow_html=True
                )

            st.markdown("---")
            st.header("🔍 검색 및 필터 옵션")

            # 1. 요양종별 필터 (기본값을 '상급종합병원'으로 설정)
            all_care_types = sorted(df['요양종별'].dropna().unique().tolist())
            if "상급종합병원" in all_care_types:
                default_care_idx = all_care_types.index("상급종합병원") + 1
            else:
                default_care_idx = 0
                
            all_care_types_with_all = ["전체"] + all_care_types
            selected_care_type = st.selectbox(
                "요양종별 선택", 
                all_care_types_with_all, 
                index=default_care_idx
            )

            # 2. 장비대분류 필터
            all_large_categories = ["전체"] + sorted(df['대분류표시'].dropna().unique().tolist())
            selected_large_category = st.selectbox("장비대분류 선택", all_large_categories)

            # 1차 필터링
            filtered_df = df.copy()
            if selected_care_type != "전체":
                filtered_df = filtered_df[filtered_df['요양종별'] == selected_care_type]
            
            if selected_large_category != "전체":
                filtered_df = filtered_df[filtered_df['대분류표시'] == selected_large_category]

            # 3. 장비세분류 필터
            if not filtered_df.empty:
                all_sub_categories = ["전체"] + sorted(filtered_df['세분류표시'].dropna().unique().tolist())
            else:
                all_sub_categories = ["전체"]
                
            selected_sub_category = st.selectbox("장비세분류 선택 (하위)", all_sub_categories)

            # 2차 필터링
            if selected_sub_category != "전체":
                filtered_df = filtered_df[filtered_df['세분류표시'] == selected_sub_category]

            # 4. 추가 검색 키워드
            search_keyword = st.text_input("요양기관명 또는 모델명 검색", placeholder="검색어를 입력하세요")
            if search_keyword:
                filtered_df = filtered_df[
                    filtered_df['요양기관명'].str.contains(search_keyword, na=False) | 
                    filtered_df['모델명'].str.contains(search_keyword, na=False)
                ]

            st.markdown("---")
            st.header("📊 정렬 및 시각화 설정")
            
            # 정렬 기준 선택 (기본값을 '모델명'으로 설정 -> 인덱스 1번)
            sort_by = st.radio("정렬 기준 선택", ["요양기관명", "모델명"], index=1)
            sort_order = st.radio("정렬 방향", ["오름차순", "내름차순"])
            is_ascending = (sort_order == "오름차순")

        # 정렬 오류 방지를 위해 정렬 대상 컬럼을 문자열(str)로 변환 후 정렬 처리
        if not filtered_df.empty:
            filtered_df[sort_by] = filtered_df[sort_by].astype(str)
            filtered_df = filtered_df.sort_values(by=sort_by, ascending=is_ascending)

        # 메인 화면 결과 표시
        st.subheader(f"📋 조회 결과 (총 {len(filtered_df):,}건)")

        view_df = filtered_df[['요양기관명', '요양종별', '대분류표시', '세분류표시', '장비허가번호', '모델명', '장비수']].rename(
            columns={
                '대분류표시': '장비대분류',
                '세분류표시': '장비세분류',
                '장비수': '수량'
            }
        )

        # 표 가로 스크롤 적용
        with st.container(border=True):
            st.dataframe(view_df, use_container_width=True, height=400)

        # 데이터 다운로드 버튼
        csv = view_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 조회 결과 CSV 다운로드",
            data=csv,
            file_name="의료장비_조회결과.csv",
            mime="text/csv",
        )

        # 📈 수량 그래프 시각화 (장비대분류가 '전체'일 경우 경고 문구 출력)
        st.markdown("---")
        st.subheader(f"📊 [{sort_by}] 별 장비 수량 시각화")

        if selected_large_category == "전체":
            st.warning("⚠️ 데이터가 방대하여 미반영-필터에서 데이터가 선택되면 표시됩니다.")
        else:
            if not filtered_df.empty:
                chart_data = filtered_df.groupby(sort_by)['장비수'].sum().reset_index()
                
                chart_width = max(800, len(chart_data) * 25)

                # 1. 막대 그래프 생성 (수량 기준 내림차순 정렬: sort='-y')
                bars = alt.Chart(chart_data).mark_bar(color='#4c78a8').encode(
                    x=alt.X(sort_by, sort='-y', title=sort_by, axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y('장비수', title='총 장비 수량'),
                    tooltip=[sort_by, '장비수']
                )

                # 2. 막대 상단 수량 텍스트 레이블 생성
                text = bars.mark_text(
                    align='center',
                    baseline='bottom',
                    dy=-5,
                    fontSize=11,
                    color='black'
                ).encode(
                    text='장비수:Q'
                )

                # 3. 레이어 결합 및 터치/줌 제한(.interactive() 제거), 화면 모드 독립 시인성 설정 적용
                chart = alt.layer(bars, text).properties(
                    width=chart_width,
                    height=450
                ).configure_axis(
                    labelColor='black',
                    titleColor='black'
                ).configure_view(
                    stroke=None
                )

                st.altair_chart(chart, use_container_width=False, theme=None)
            else:
                st.info("시각화할 데이터가 없습니다.")