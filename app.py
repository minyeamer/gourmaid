import json
import pandas as pd
import re
import streamlit as st
import streamlit.components.v1 as components
from admin import KakaoAdmin
from api import get_service_keys


def load_main_page(session: st.AutoSessionState, admin: KakaoAdmin):
    """
    맛집 검색 페이지를 불러오는 함수
    """

    if not session:
        session.search = False
        session.page = 0

    st.markdown("""
                <h1>Gourmaid
                <img src="https://cleanmyhouse.biz/wp-content/uploads/2018/01/Logomakr_4F0qnR.png"
                     width="8%" style="margin-left:0.1rem;margin-bottom:3rem;">
                </h1>
                """,unsafe_allow_html=True)

    # 배너 이미지
    st.image('https://i.gifer.com/ZWnN.gif')

    target, keywords = st.columns([1,4])
    with target:
        option_names = ['일반 검색','식당명 검색','메뉴 검색','리뷰 검색','전체 검색']
        st.selectbox(label='', options=option_names, key='target')
    with keywords:
        # 키워드를 입력하지 않으면 전체 서비스 데이터 표시
        st.text_input(label='', max_chars=30, key='keywords')

    # 서비스 데이터가 커지면 보고 싶은 맛집 수를 제어할 필요가 있음
    # st.slider('보고 싶은 맛집 수를 설정해주세요.', 1, 30, 3, key='display')

    exact, margin, search = st.columns([2,7,1])
    with exact:
        st.checkbox('키워드와 일치', key='exact')
    with search:
        search_bt = st.button('검색')

    # 서비스 지역 확대 시 Geolocation API를 사용하여 위치 기반 검색 구현
    # lat = gps['location']['lat']
    # lng = gps['location']['lng']

    # 서비스 데이터가 커지면 키워드를 반드시 입력하도록 검색 조건 변경
    if search_bt:
        try:
            session.data = admin.advanced_search(keywords=session.keywords.split(),
                                                 target=session.target,
                                                 exact=session.exact)
            session.search = True
            session.page = 0
        except Exception as e:
            print(e) # 에러 메시지 로그 기록
            session.search = False
            st.markdown(f"<center><h3>{e}</h3></center>",unsafe_allow_html=True)
            load_debug_div(session, unfold=True)


def load_result_page(session: st.AutoSessionState, admin: KakaoAdmin):
    """
    맛집 검색 결과 페이지를 불러오는 함수
    """

    st.markdown('---')

    # 플랫폼 한계상 이전/다음 버튼 위치 선정 및 제어가 원활하지 않음
    prev, margin, next = st.columns([1,8,1])
    with prev:
        prev_bt = st.button('이전', disabled=(not session.page))
    with next:
        next_bt = st.button('다음', disabled=(session.page > len(session.data)-2))

    if prev_bt:
        session.page -= 1
    if next_bt:
        session.page += 1

    load_summary_div(session)
    load_list_div(session, '메뉴')
    load_kakao_map(session, admin)
    load_list_div(session, '리뷰')
    load_debug_div(session)


def load_summary_div(session: st.AutoSessionState):
    """
    맛집 검색 결과 중 요약 정보에 해당하는 부분을 불러오는 함수
    """

    if session.data['이미지 주소'][session.page]:
        components.html(f"""
                            <a href="{session.data['웹페이지 주소'][session.page]}" target="_blank">
                            <img src={session.data['이미지 주소'][session.page]}
                                style="margin-top:-20%;margin-left:-8%">
                            </a>""",width=None,height=280)

    st.markdown(f"<center><h1>{session.data['식당명'][session.page]}</h1></center>",
                unsafe_allow_html=True)

    lmargin, category, raiting, review_num, rmargin = st.columns([2,2,2,2,2])

    with category:
        st.markdown("<center><h5>{}</h5></center>".format(
                        session.data['분류명'][session.page].split(' > ')[-1]),
                    unsafe_allow_html=True)
    with raiting:
        st.markdown("<center><h5>별점 {}</h5></center>".format(
                        session.data['별점'][session['page']]),
                    unsafe_allow_html=True)
    with review_num:
        st.markdown("<center><h5>리뷰 {}</h5></center>".format(
                        session.data['리뷰 수'][session['page']]+
                        session.data['블로그 리뷰 수'][session['page']]),
                    unsafe_allow_html=True)

    lmargin, sentiment_gauge, rmargin = st.columns([2,6,2])
    with sentiment_gauge:
        total_review = session.data['리뷰 수'][session['page']]
        total_review = total_review if total_review else 1
        negative_review = session.data['부정 리뷰 수'][session['page']]
        st.progress(int((total_review-negative_review)/(total_review)*100))


def load_list_div(session: st.AutoSessionState, name: str):
    """
    맛집 검색 결과 중 목록에 해당하는 부분을 불러오는 함수
    """

    if session.data[name][session.page]:
        st.markdown('---')
        st.markdown(f"<center><h3>{name}</h3></center>",unsafe_allow_html=True)
        st.markdown('&nbsp;')

        left_div, right_div = st.columns(2)

        # 데이터프레임을 직접 가져올 때 리스트가 문자열로 합쳐지는 문제에 대한 대비책
        # item_list = session.data[name][session.page].replace('"',"'")
        # item_list = re.search("\['(.*)'\]",item_list)
        # item_list = item_list[1].split("', '")

        for i, item in enumerate(session.data[name][session.page][:20]):
            if i%2 == 0:
                with left_div:                    
                    st.markdown(f"<center><p>{item}</p></center>",unsafe_allow_html=True)
            else:
                with right_div:                    
                    st.markdown(f"<center><p>{item}</p></center>",unsafe_allow_html=True)


def load_kakao_map(session: st.AutoSessionState, admin: KakaoAdmin):
    """
    맛집 검색 결과 중 카카오 지도에 해당하는 부분을 불러오는 함수
    """

    st.markdown('---')

    service_url = admin.service_info['urls']['kakao_map']
    service_key = admin.service_info['keys']['kakao_js']
    kakao_x = session.data['x'][session.page]
    kakao_y = session.data['y'][session.page]

    kakao_map =  """
                 <div id="map" style="width:100%;height:480px;"></div>
                 <script type="text/javascript"
                         src="{url}?appkey={key}"></script>
                 <script>
                 var mapContainer = document.getElementById('map'),
                     mapOption = {{
                         center: new kakao.maps.LatLng({y}, {x}),
                         level: 3
                     }};

                 var map = new kakao.maps.Map(mapContainer, mapOption);

                 var marker = new kakao.maps.Marker({{ 
                     position: map.getCenter() 
                 }}); 
                 marker.setMap(map);
                 </script>
                 """.format(url=service_url,key=service_key,x=kakao_x,y=kakao_y)

    components.html(kakao_map, width=None, height=400, scrolling=False)

    st.markdown("<center><h5>📍&nbsp;&nbsp;{}</h5></center>".format(
                    session.data['도로명 주소'][session['page']]),
                unsafe_allow_html=True)

    if session.data['전화번호'][session['page']]:
        st.markdown("<center><h5>📞&nbsp;&nbsp;{}</h5></center>".format(
                        session.data['전화번호'][session['page']]),
                    unsafe_allow_html=True)


def load_debug_div(session: st.AutoSessionState, unfold=False):
    """
    맛집 검색 결과에 대한 디버깅 정보를 불러오는 함수
    """

    st.markdown('---')

    lmargin, debug, rmargin = st.columns([8,2,8])
    with debug:
        debug_bt = st.button('DEBUG')

    if debug_bt or unfold:
        st.markdown("<center><h3>DataFrame</h3></center>",unsafe_allow_html=True)
        st.dataframe(session.data)
        st.markdown("<center><h3>Session Info</h3></center>",unsafe_allow_html=True)
        st.session_state


def main():
    """
    서비스 데이터를 관리하는 관리자 객체를 생성하고 검색 서비스를 실행하는 메인 함수
    """

    # API 키는 개인정보 문제로 숨김 처리
    service_keys = get_service_keys()

    # 프로젝트 시간 제약에 의해 서비스 지역을 서울시 강남구 삼성동으로 한정
    # local_info = {'si': '서울특별시', 'gu': '강남구', 'dong': '삼성동', 'address': ['서울 강남구 삼성동']}

    # 개인적인 목적으로 광명동 맛집을 탐색하기 위해 설정, 향후 서비스 확대 시 서울 외 지역 간 호환을 위해 파라미터 재조정 필요
    gm_local_info = {'si': '경기도', 'gu': '광명시', 'dong': '',
                     'address': ['경기 광명시 광명동']}

    admin = KakaoAdmin('minyeamer','abcd@likelion.org',service_keys,gm_local_info)

    try:
        # 스크래핑이 필요한 경우 (디버그 시 size 파라미터를 사용해 요청할 데이터 수 제한)
        # admin.set_service_data()

        # 스크래핑한 데이터가 있을 경우
        with open('data/gm_service_data.json','r', encoding='UTF-8') as f:
            service_data = json.load(f)
        # 데이터프레임을 직접 가져올 경우 리스트가 하나의 문자열로 합쳐지는 문제 발생
        # service_df = pd.read_csv('data/service_data.csv')
        admin.set_service_data(service_data)
    except Exception as e:
        print(type(e), e) # 에러 메시지 로그 기록

    try:
        # 웹서비스 구동
        load_main_page(st.session_state, admin)

        if st.session_state.search:
            load_result_page(st.session_state, admin)
    except Exception as e:
        print(e) # 에러 메시지 로그 기록
        st.markdown(f"<center><h3>404 Not Found</h3></center>",unsafe_allow_html=True)


if __name__ == '__main__':
    main()
