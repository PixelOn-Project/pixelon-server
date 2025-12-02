# PixelOn (KR)

## What is PixelOn?
![PixelOn Main](imgs/1.png)

**PixelOn**은 PixelArt Editor인 **Piskel**에 **On-Device** 이미지 생성 기능을 추가한 확장 기능입니다.
이를 통해 사용자는 언제 어디서든 쉽고 빠르게 AI 이미지 생성 기능을 활용하여 픽셀 아트를 만들 수 있습니다.

여러분들의 표현력을 더 높여보세요!

우리는 Stable Diffusion C++를 이용해 가볍고 빠른 이미지 생성 기능을 구현했습니다. 이를 Piskel과 결합하여 끊임없는 창작 경험을 제공합니다. 또한 아이들의 상상력을 더욱 풍부하게 해주기 위해 'Layer 내보내기' 기능을 통해 생성된 이미지를 컬러링 북처럼 활용할 수도 있습니다.

이 프로젝트는 컴퓨터 기술의 발전과 가정 내 GPU 보급률 증가에 발맞추어, 지속적인 구독료를 요구하는 클라우드 기반 생성기 대신 누구나 쉽게 자신의 컴퓨터에서 생성형 AI를 활용할 수 있도록 기획 및 개발되었습니다.

### 주요 기능
* **AI 이미지 생성:** 텍스트 프롬프트를 통해 픽셀 아트 생성
* **호환성:** 기존 `.piskel` 파일과 완벽 호환
* **내보내기:** 생성된 이미지를 즉시 Editor 레이어로 내보내기

### System Requirements (Minimum & Recommended)
| 구분 | 최소 사양 | 권장 사양 |
| :--- | :--- | :--- |
| **CPU** | Intel i5 이상 | Intel i5 이상 |
| **RAM** | 16GB 이상 | 16GB 이상 |
| **GPU** | NVIDIA RTX 2000번대 이상 (VRAM 4GB 이상) | NVIDIA RTX 3070 이상 |
| **Disk** | 여유공간 20GB+ 필요 | 여유공간 20GB+ 필요 |

> **Notice 1:** CPU만으로도 생성 기능을 사용할 수 있으나, 장당 2~3분 이상의 시간이 소요될 수 있습니다. (RTX 2060 기준 약 10초 소요)
> **Notice 2:** AMD GPU 지원은 추후 업데이트될 예정입니다.

### Open Source Credits
* [Stable Diffusion C++](https://github.com/leejet/stable-diffusion.cpp)
* [Piskel](https://www.piskelapp.com/)
    * [PixelOn Piskel Repository](URL_HERE)
* **Stable Diffusion Models**
    * [LORA Model](URL_HERE)
    * 그 외 활용된 모델들

---

## How to install Piskel & PixelOn?
![PixelOn Installer](imgs/2.png)
1. **[PixelOn Installer 다운로드](URL_HERE)**를 클릭하여 설치 파일을 받습니다.
2. 설치 프로그램을 실행하면 시스템을 자동으로 스캔하여 최적의 가속화 버전(CUDA 등)을 선택합니다.
3. 설치가 완료되면 바탕화면의 **PixelOn**을 실행합니다.

### Q & A
* **Q. Nvidia GPU인데 CUDA가 선택되지 않습니다.**
    * A. GPU 드라이버 버전이 낮을 수 있습니다. [Nvidia 드라이버 다운로드](https://www.nvidia.com/Download/index.aspx)에서 최신 버전으로 업데이트해주세요.
* **Q. 서버 연결에 실패했다고 나옵니다.**
    * A. 네트워크 이슈로 설치 과정에서 누락된 파일이 있을 수 있습니다. 설치 프로그램을 통해 다시 설치해주세요.
* **Q. 생성 속도가 너무 느립니다.**
    * A. GPU 가속기가 없거나 사양을 충족하지 못할 경우 속도가 느릴 수 있습니다. 이는 로컬 구동 방식의 물리적 한계입니다.

---

## How to Use PixelOn?

### 1. Piskel Editor
PixelOn을 실행하면 Piskel 에디터 화면이 나타납니다. 기존 Piskel 사용법과 동일하게 도트 작업을 수행할 수 있습니다. 자세한 사용 방법은 **[Piskel 공식 가이드](https://www.piskelapp.com/wiki/help)**를 참고해주세요.

### 2. Simple Prompt
![Simple Prompt UI](imgs/3.png)
에디터 하단의 프롬프트 창을 이용해 빠르게 이미지를 생성할 수 있습니다. 이 창에서는 **Positive Prompt(긍정 명령어)**만 입력 가능합니다.

### 3. Detail Dialog
![Detail Dialog UI](imgs/4.png)
더 정교한 작업을 원한다면 Detail 창을 엽니다. 각 구성 요소의 상세 설명은 아래와 같습니다.

<br>

<table>
<tr>
<td width="50%" valign="top">
    <img src="imgs/5.png" alt="History UI" style="max-width:100%;">
</td>
<td width="50%" valign="top">
    <h3>ⓐ History Management</h3>
    <p><b>History</b> 탭에서 이전 작업 세션을 관리합니다.</p>
    <ul>
        <li><b>세션 클릭:</b> 과거 생성 기록을 조회합니다.</li>
        <li><b>... 버튼:</b> 세션 이름을 변경하거나 삭제합니다.</li>
        <li><b>주의:</b> 삭제 시 복구(Undo)가 불가능하므로 신중하게 결정해주세요.</li>
    </ul>
</td>
</tr>
</table>

<br>

<table>
<tr>
<td width="50%" valign="top">
    <img src="imgs/6.png" alt="Settings UI" style="max-width:100%;">
</td>
<td width="50%" valign="top">
    <h3>ⓑ Prompt & Settings</h3>
    <p>이미지 생성의 핵심 설정을 조작합니다.</p>
    <ul>
        <li><b>Positive Prompt:</b> 생성할 장면 묘사 (태그 형식, Enter 구분)</li>
        <li><b>Negative Prompt:</b> 제외할 요소 작성 (예: 저화질 등)</li>
        <li><b>Preset:</b> 상황에 맞는 모델 프리셋 선택 (Normal, Pixel Art 등)</li>
        <li><b>Resolution / Count:</b> 이미지 크기와 생성 개수 조절</li>
    </ul>
    <blockquote><b>주의:</b> 해상도가 너무 작으면 이미지가 정상적으로 생성되지 않을 수 있습니다.</blockquote>
</td>
</tr>
</table>

<br>

<table>
<tr>
<td width="50%" valign="top">
    <img src="imgs/7.png" alt="Results UI" style="max-width:100%;">
</td>
<td width="50%" valign="top">
    <h3>ⓒ Results</h3>
    <p>생성된 이미지를 확인하고 관리합니다.</p>
    <ul>
        <li><b>좌클릭:</b> 이미지 선택</li>
        <li><b>... 클릭 (이미지 상단):</b>
            <ul>
                <li><i>Transfer:</i> 생성 당시 설정 불러오기</li>
                <li><i>Delete:</i> 해당 이미지 삭제</li>
            </ul>
        </li>
        <li><b>Cancel:</b> 이미지 선택 해제</li>
        <li><b>Delete Selected:</b> 선택된 이미지 일괄 삭제</li>
    </ul>
    <blockquote><b>주의:</b> 삭제 시 복구(Undo)가 불가능합니다.</blockquote>
</td>
</tr>
</table>

<br>

<table>
<tr>
<td width="50%" valign="top">
    <img src="imgs/8.png" alt="Log UI" style="max-width:100%;">
</td>
<td width="50%" valign="top">
    <h3>ⓓ Log, Expert</h3>
    <p>작동 로그를 확인하거나 이미지를 Editor로 보냅니다.</p>
    <ul>
        <li><b>Move To Frame:</b> 선택된 이미지들을 각각 <b>새로운 프레임</b>으로 내보냅니다. (여러 장 작업 시 유용)</li>
        <li><b>Move To Layer:</b> 마지막 선택 이미지를 <b>현재 레이어</b>로 내보냅니다. (한 장 작업 시 유용)</li>
    </ul>
</td>
</tr>
</table>

<br>

## Development Environment

### Prerequisites
* Windows OS
* Python >= 3.10
* Node.js
*(We build on Python 3.14 and Node 24.11.1)*

### How to setup
1. 위 전제 조건을 만족하는 환경을 준비합니다.
2. `bootstrap.bat`을 실행하여 필요한 종속성 파일을 설치합니다.
    * 포함 항목: Stable Diffusion C++, Piskel (Forked Repo), AI Models
3. `python app.py`를 입력하여 로컬 서버를 실행합니다.

### Contribute
기여를 원하신다면 `dev` 브랜치를 사용해주세요. Pull Request는 언제나 환영합니다!

## License
이 프로젝트는 [MIT License](LICENSE)를 따릅니다.