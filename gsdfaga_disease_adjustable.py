import sys
import json
import os
import unicodedata
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk
import requests

BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config_seasonal.json")
RISK_CONFIG_FILE = os.path.join(BASE_DIR, "risk_thresholds.json")

# 病害判定の数値はこの設定から読み込みます。
# GUIの「判定数値を変更」から変更・保存でき、次回起動後も維持されます。
DEFAULT_RISK_SETTINGS = {
    "black_spot": {
        "temp_min": 10.0, "temp_max": 32.0,
        "temp_opt_min": 18.0, "temp_opt_max": 26.0,
        "temp_good_min": 14.0, "temp_good_max": 29.0,
        "wet_t1": 2.0, "wet_t2": 4.0, "wet_t3": 6.0, "wet_t4": 8.0,
        "wet_scores": "0,1,2,4,5",
        "rain_floor": 30.0, "wet_floor": 4.0, "floor_score": 2.0,
        "long_wet_hours": 6.0, "long_wet_temp_min": 18.0, "long_wet_temp_max": 27.0,
        "long_wet_floor": 3.0,
    },
    "powdery_open": {
        "temp_min": 8.0, "temp_max": 31.0,
        "best_min": 20.0, "best_max": 27.0,
        "mid_min": 15.0, "mid_max": 28.5,
        "low_min": 10.0, "low_max": 30.0,
        "base_scores": "1,2,4,5",
        "hum_t1": 60.0, "hum_t2": 70.0, "hum_t3": 80.0, "hum_t4": 90.0,
        "hum_factors": "0,0.25,0.50,0.80,1.00",
        "rain_t1": 10.0, "rain_t2": 30.0, "rain_t3": 60.0,
        "rain_minus": "0,1,1,2",
    },
    "powdery_roof": {
        "temp_min": 8.0, "temp_max": 31.0,
        "best_min": 20.0, "best_max": 27.0,
        "mid_min": 15.0, "mid_max": 28.5,
        "low_min": 10.0, "low_max": 30.0,
        "base_scores": "1,3,5,6",
        "hum_t1": 60.0, "hum_t2": 70.0, "hum_t3": 80.0, "hum_t4": 90.0,
        "hum_factors": "0,0.30,0.55,0.85,1.00",
    },
    "downy": {
        "temp_min": 5.0, "temp_max": 28.0,
        "opt_min": 15.0, "opt_max": 20.0,
        "good_min": 10.0, "good_max": 25.0,
        "edge_min": 5.0, "edge_max": 28.0,
        "temp_factors": "0.35,0.75,1.00",
        "hum_t1": 70.0, "hum_t2": 75.0, "hum_t3": 80.0, "hum_t4": 85.0, "hum_t5": 90.0,
        "hum_factors": "0.08,0.20,0.45,0.75,1.00,1.15",
        "wet_t1": 2.0, "wet_t2": 4.0, "wet_t3": 6.0, "wet_t4": 8.0,
        "wet_factors": "0.15,0.45,0.75,1.00,1.20",
        "rain_t1": 10.0, "rain_t2": 30.0, "rain_t3": 60.0,
        "rain_factors": "0.65,0.85,1.00,1.05",
        "min_wet_warning": 6.0, "min_hum_warning": 75.0, "warning_floor": 1.0,
        "min_wet_danger2": 8.0, "min_hum_danger2": 80.0, "danger2_floor": 2.0,
        "hot_reduction_start": 30.0, "hot_reduction_hours": 2.0, "hot_factor": 0.60,
        "very_hot_hours": 4.0, "very_hot_factor": 0.40,
    },
    "rust": {
        "temp_min": 8.0, "temp_max": 25.0,
        "opt_min": 14.0, "opt_max": 20.0,
        "good_min": 10.0, "good_max": 23.0,
        "wet_t1": 1.0, "wet_t2": 2.0, "wet_t3": 4.0, "wet_t4": 6.0,
        "wet_scores": "0,1,2,3,4",
        "hum_t1": 70.0, "hum_t2": 80.0, "hum_t3": 90.0,
        "hum_factors": "0.30,0.60,0.85,1.00",
        "rain_bonus_threshold": 30.0,
        "rain_bonus": 1.0,
        "floor_temp_min": 14.0, "floor_temp_max": 20.0,
        "floor_wet_hours": 4.0, "floor_hum": 80.0, "floor_score": 2.0,
    },
}


def load_risk_settings():
    import copy
    settings = copy.deepcopy(DEFAULT_RISK_SETTINGS)
    if os.path.exists(RISK_CONFIG_FILE):
        try:
            with open(RISK_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for disease, vals in saved.items():
                if disease in settings and isinstance(vals, dict):
                    for key, value in vals.items():
                        if key in settings[disease]:
                            settings[disease][key] = value
        except Exception:
            pass
    return settings


def save_risk_settings(settings):
    try:
        with open(RISK_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


RISK_SETTINGS = load_risk_settings()

# 取得データの説明をメイン画面に表示するための情報
DATA_INFO = {
    "requested_lat": None, "requested_lon": None,
    "data_lat": None, "data_lon": None, "elevation": None,
    "timezone": "Asia/Tokyo", "start_year": None, "end_year": None,
    "years": None, "dataset": "ERA5-Land（長期比較向け）",
}


# ============================================================
# 設定データの保存・読み込み
# ============================================================
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"lat": "", "lon": ""}


def save_config(lat, lon):
    data = {"lat": str(lat), "lon": str(lon)}
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ============================================================
# 右クリックメニュー＆貼り付け機能
# ============================================================
def paste_to_entry(entry_widget):
    try:
        clipboard_text = root.clipboard_get()
        cleaned_text = unicodedata.normalize("NFKC", clipboard_text).strip()
        try:
            entry_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass
        entry_widget.insert(tk.INSERT, cleaned_text)
    except Exception:
        pass


def show_context_menu(event):
    widget = event.widget
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(
        label="切り取り", command=lambda: widget.event_generate("<<Cut>>")
    )
    menu.add_command(
        label="コピー", command=lambda: widget.event_generate("<<Copy>>")
    )
    menu.add_command(label="貼り付け", command=lambda: paste_to_entry(widget))
    menu.add_separator()
    menu.add_command(
        label="すべて選択", command=lambda: widget.select_range(0, tk.END)
    )
    menu.post(event.x_root, event.y_root)


# ============================================================
# 判定基準・ロジック解説サブウィンドウ
# ============================================================
def open_criteria_window():
    sub_win = tk.Toplevel(root)
    sub_win.title("病害リスク・備考の判定基準 ＆ 算出ロジック一覧")
    sub_win.geometry("820x680")
    sub_win.lift()
    sub_win.focus_force()

    frame = tk.Frame(sub_win)
    frame.pack(fill="both", expand=True)
    scroll = ttk.Scrollbar(frame, orient="vertical")
    txt = tk.Text(frame, font=("メイリオ", 9), yscrollcommand=scroll.set, padx=12, pady=12)
    scroll.config(command=txt.yview)
    scroll.pack(side="right", fill="y")
    txt.pack(side="left", fill="both", expand=True)

    def _v(disease, key, default="-"):
        try:
            return RISK_SETTINGS[disease][key]
        except Exception:
            return default

    criteria_text = f"""【病害リスク判定ロジック一覧（0:安全 ～ 6:危険）】

この画面では、旬（上旬・中旬・下旬）ごとの気象データを使い、
「温度・湿度・降水量・推定葉濡れ時間」を病害ごとの判定式に入れて、0～6の相対リスク指数に変換しています。

重要：この0～6は発病確率（％）ではありません。研究機関が定めた公式の危険度ではなく、
このプログラムで設定した気象条件を数値化した「相対リスク指数」です。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【1．データをどう作っているか】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
● 入力した緯度・経度（WGS84）の地点付近から、Open-Meteo Historical Weather APIのERA5-Landを取得します。
● ERA5-Landは約11km（0.1度）の格子データです。実際には指定座標に対応するグリッドのデータを使用します。
● 現在年を除く直近11年間を対象にします。2026年なら2015～2025年です。
● 各月を「上旬・中旬・下旬」に分けます。
● 気温・湿度：対象期間の同じ旬について平均します。
● 降水量：各年のその旬の降水量を合計し、その11年分を平均します。
● したがって、表に表示される値は「過去11年間の同じ旬の平均的な気象条件」です。
● 気象庁などの正式な「平年値」は通常30年平均なので、このプログラムでは「過去11年平均」と表示しています。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【2．葉濡れ時間をどう計算しているか】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
実際の葉面濡れセンサーは使っていないため、「葉濡れ候補時間」という代理指標を作っています。

1時間ごとのデータについて、
  「相対湿度 ≧ 90％」
  または
  「1時間降水量 ＞ 0.1mm」
のどちらかを満たした時間を、葉が濡れている可能性が高い時間としてカウントします。

旬全体の葉濡れ候補時間 ÷ その旬の日数
＝「推定葉濡れ時間（時間/日）」

さらに、べと病用として、
● 20℃未満の葉濡れ時間
● 15～20℃の葉濡れ時間
● 30℃超の時間
も別々に集計しています。

※これは「葉濡れ実測値」ではなく、病害判定のための推定値です。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【3．黒点病の計算】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
黒点病は「葉濡れ」を中心に判定します。
研究・普及資料でも、黒点病は葉面の水分が重要で、約6～7時間以上の葉濡れが感染に重要とされています。
citeturn0search0turn0search4turn0search9

計算の流れ：
① 平均気温が判定範囲外 → 0
② 葉濡れ時間から「葉濡れ点」を決定
③ 平均気温から「温度係数」を決定
④ 葉濡れ点 × 温度係数 ＝ 基本リスク
⑤ 雨量＋葉濡れが一定条件を満たす場合、最低リスクを保証
⑥ 長時間葉濡れ＋適温の場合も最低リスクを保証
⑦ 最後に四捨五入して0～6に制限

現在の黒点病設定値：
  判定温度：{_v("black_spot","temp_min")}～{_v("black_spot","temp_max")}℃
  最適温度：{_v("black_spot","temp_opt_min")}～{_v("black_spot","temp_opt_max")}℃ → 温度係数1.00
  好適温度：{_v("black_spot","temp_good_min")}～{_v("black_spot","temp_good_max")}℃ → 温度係数0.75
  その他の判定範囲 → 温度係数0.40
  葉濡れ境界：{_v("black_spot","wet_t1")} / {_v("black_spot","wet_t2")} / {_v("black_spot","wet_t3")} / {_v("black_spot","wet_t4")} 時間/日
  葉濡れ点数：{_v("black_spot","wet_scores")}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【4．うどんこ病の計算】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
うどんこ病は黒点病とは違い、「長時間の葉濡れ」を主条件にはしません。
温度と高湿度を中心に判定し、露地では雨による洗い流しを減点します。
バラのうどんこ病は中程度の温度＋高湿度で発生しやすく、自由水を必要としない点が黒点病などと異なります。
citeturn0search1turn0search2turn0search13

計算の流れ：
① 平均気温が判定範囲外 → 0
② 気温帯から「基本点」を決定
③ 平均湿度から「湿度係数」を決定
④ 基本点 × 湿度係数 ＝ リスク
⑤ 露地のみ、旬の降水量に応じて雨の洗い流し分を減点
⑥ 0～6に制限

【露地と軒下の違い】
● 露地：雨が直接当たるため、降水量による減点あり
● 軒下：雨による洗い流しの影響を小さく設定

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【5．べと病の計算】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
べと病は、このプログラムで最も複数の条件を組み合わせている病害です。
バラべと病では15～20℃付近が感染に適し、葉濡れが重要です。研究では20℃未満の葉濡れ時間や30℃超の時間を含む10日累積値を使った予測モデルも報告されています。
citeturn0search7turn0search3

基本式は、
  6 × 温度係数 × 湿度係数 × 20℃未満葉濡れ係数 × 雨量係数
  ＝ 基本リスク
です。

さらに、
● 15～20℃の葉濡れが少ない場合 → 過大評価を抑制
● 30℃超の時間が多い場合 → 高温による抑制を反映
● 適温＋十分な葉濡れ＋高湿度 → 最低「警戒1」を保証
● さらに強い条件 → 最低「危険2」を保証
という補正を行います。

現在の判定では、単に「平均気温が20℃だから危険」とはせず、時間別データを使って真夏の過大評価を抑える設計です。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【6．さび病の計算】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
さび病は「涼しい・湿った条件」を中心に評価します。
バラのさび病は冷涼で湿潤な天候を好み、葉濡れが感染に重要です。
citeturn0search0turn0search4turn0search5

基本式は、
  葉濡れ点 × 温度係数 × 湿度係数
  ＝ 基本リスク
です。

さらに、一定以上の雨量がある場合は加点し、
「適温＋一定時間の葉濡れ＋高湿度」の条件を満たす場合は最低リスクを保証します。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【7．最終的に「安全0～危険6」にする方法】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
各病害で計算した「raw（生のリスク値）」を、
  int(round(raw))
で四捨五入し、
  0～6
の範囲に収めます。

表示は、
  0 → 安全0
  1 → 警戒1
  2～6 → 危険2～危険6
です。

つまり「危険5」は「発病確率5割」などの意味ではありません。
「このプログラムが設定した気象条件の組み合わせから見て、相対的にかなり病害に適した条件」という意味です。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【8．判定数値を変更した場合】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
メイン画面の「判定数値を変更」から、温度・湿度・葉濡れ時間・雨量・各係数・最低リスク保証などを変更できます。
保存した値は risk_thresholds.json に保存され、次回起動後も読み込まれます。

この「判定基準を見る」画面に表示される数値は、現在読み込まれている設定値を反映しています。
そのため、数値を変更した後は、もう一度この画面を開くと現在の判定基準を確認できます。

【注意】
この診断は「気象条件から見た病害リスクの相対評価」です。品種の耐病性、既存病斑、株の込み具合、日照、風通し、実際の葉面濡れ、病原菌の存在量などは完全には評価できません。
したがって、実際の発病を保証するものではなく、地域ごとの「病害が発生しやすい気象条件」を比較するための指標として利用してください。
"""
    txt.insert("1.0", criteria_text)
    txt.config(state="disabled")


def open_risk_settings_window():
    global RISK_SETTINGS
    win = tk.Toplevel(root)
    win.title("病害判定数値の変更")
    win.geometry("920x700")
    win.lift()
    win.focus_force()

    outer = ttk.Frame(win, padding=10)
    outer.pack(fill="both", expand=True)
    ttk.Label(outer, text="ここで変更した数値が病害判定に使われます。保存すると次回起動後も維持されます。", font=("メイリオ", 10, "bold")).pack(anchor="w", pady=(0,8))

    canvas2 = tk.Canvas(outer, highlightthickness=0)
    bar2 = ttk.Scrollbar(outer, orient="vertical", command=canvas2.yview)
    inner = ttk.Frame(canvas2)
    canvas2.create_window((0,0), window=inner, anchor="nw")
    canvas2.configure(yscrollcommand=bar2.set)
    canvas2.pack(side="left", fill="both", expand=True)
    bar2.pack(side="right", fill="y")

    entries = {}
    labels = {
        "black_spot": "黒点病", "powdery_open": "うどんこ病（露地）",
        "powdery_roof": "うどんこ病（軒下）", "downy": "べと病", "rust": "さび病"
    }
    field_labels = {
        "temp_min":"判定最低気温（℃）", "temp_max":"判定最高気温（℃）",
        "temp_opt_min":"最適温度・下限（℃）", "temp_opt_max":"最適温度・上限（℃）",
        "temp_good_min":"好適温度・下限（℃）", "temp_good_max":"好適温度・上限（℃）",
        "opt_min":"最適温度・下限（℃）", "opt_max":"最適温度・上限（℃）",
        "good_min":"好適温度・下限（℃）", "good_max":"好適温度・上限（℃）",
        "edge_min":"判定温度・下限（℃）", "edge_max":"判定温度・上限（℃）",
        "best_min":"最適温度・下限（℃）", "best_max":"最適温度・上限（℃）",
        "mid_min":"中程度温度・下限（℃）", "mid_max":"中程度温度・上限（℃）",
        "low_min":"低め温度・下限（℃）", "low_max":"低め温度・上限（℃）",
        "wet_t1":"葉濡れ時間・境界1（時間/日）", "wet_t2":"葉濡れ時間・境界2（時間/日）",
        "wet_t3":"葉濡れ時間・境界3（時間/日）", "wet_t4":"葉濡れ時間・境界4（時間/日）",
        "wet_scores":"葉濡れ時間ごとの点数（カンマ区切り）",
        "rain_floor":"雨量による最低判定境界（mm）", "wet_floor":"最低判定に必要な葉濡れ（時間/日）",
        "floor_score":"最低リスク点数", "long_wet_hours":"長時間葉濡れ境界（時間/日）",
        "long_wet_temp_min":"長時間葉濡れ時の温度下限（℃）", "long_wet_temp_max":"長時間葉濡れ時の温度上限（℃）",
        "long_wet_floor":"長時間葉濡れ時の最低リスク",
        "base_scores":"温度帯ごとの基本点数（カンマ区切り）",
        "hum_t1":"湿度・境界1（%）", "hum_t2":"湿度・境界2（%）", "hum_t3":"湿度・境界3（%）",
        "hum_t4":"湿度・境界4（%）", "hum_t5":"湿度・境界5（%）",
        "hum_factors":"湿度による係数（カンマ区切り）",
        "rain_t1":"雨量・境界1（mm）", "rain_t2":"雨量・境界2（mm）", "rain_t3":"雨量・境界3（mm）",
        "rain_minus":"雨量による減点（カンマ区切り）",
        "temp_factors":"温度による係数（カンマ区切り）",
        "wet_factors":"葉濡れによる係数（カンマ区切り）",
        "rain_factors":"雨量による係数（カンマ区切り）",
        "min_wet_warning":"警戒1を保証する葉濡れ（時間/日）", "min_hum_warning":"警戒1を保証する湿度（%）",
        "warning_floor":"警戒時の最低リスク", "min_wet_danger2":"危険2を保証する葉濡れ（時間/日）",
        "min_hum_danger2":"危険2を保証する湿度（%）", "danger2_floor":"危険2時の最低リスク",
        "hot_reduction_start":"高温抑制開始温度（℃）", "hot_reduction_hours":"高温抑制開始時間（時間/日）",
        "hot_factor":"高温時の係数", "very_hot_hours":"強い高温抑制時間（時間/日）", "very_hot_factor":"強い高温時の係数",
        "rain_bonus_threshold":"雨量加点開始（mm）", "rain_bonus":"雨量による加点",
        "floor_temp_min":"最低リスク保証・温度下限（℃）", "floor_temp_max":"最低リスク保証・温度上限（℃）",
        "floor_wet_hours":"最低リスク保証・葉濡れ（時間/日）", "floor_hum":"最低リスク保証・湿度（%）",
        "floor_score":"最低リスク保証の点数",
    }

    descriptions = {
        "black_spot":"葉濡れと温度を中心に黒点病の相対リスクを計算します。",
        "powdery_open":"露地条件。湿度を考慮し、雨による洗い流しを減点します。",
        "powdery_roof":"軒下条件。雨による洗い流しの影響を小さくしています。",
        "downy":"15～20℃・高湿度・20℃未満の葉濡れを特に重視します。",
        "rust":"14～20℃・葉濡れ・高湿度を中心に評価します。",
    }

    for disease, vals in RISK_SETTINGS.items():
        lf = ttk.LabelFrame(inner, text=labels.get(disease, disease), padding=8)
        lf.pack(fill="x", padx=4, pady=5)
        ttk.Label(lf, text=descriptions.get(disease, ""), foreground="#555555").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=4, pady=(0,6)
        )
        row = 1
        entries[disease] = {}
        for key, value in vals.items():
            display = field_labels.get(key, key)
            ttk.Label(lf, text=display, width=38).grid(row=row, column=0, sticky="w", padx=4, pady=2)
            ent = ttk.Entry(lf, width=22)
            ent.insert(0, str(value))
            ent.grid(row=row, column=1, sticky="w", padx=4, pady=2)
            entries[disease][key] = ent
            row += 1

    def save_values():
        global RISK_SETTINGS
        new_settings = {}
        try:
            for disease, vals in entries.items():
                new_settings[disease] = {}
                for key, ent in vals.items():
                    text = ent.get().strip()
                    if key in ("wet_scores", "base_scores", "hum_factors", "temp_factors", "wet_factors", "rain_factors", "rain_minus"):
                        parts = [x.strip() for x in text.split(",") if x.strip()]
                        if not parts:
                            raise ValueError(f"{disease}/{key}")
                        new_settings[disease][key] = ",".join(parts)
                    else:
                        new_settings[disease][key] = float(text)
            if not save_risk_settings(new_settings):
                raise ValueError("ファイル保存に失敗しました")
            RISK_SETTINGS = new_settings
            messagebox.showinfo("保存完了", "病害判定の数値を保存しました。\n次回の診断から新しい数値が使われます。", parent=win)
        except Exception as e:
            messagebox.showerror("入力エラー", f"数値を確認してください。\n{e}", parent=win)

    def reset_values():
        nonlocal entries
        for disease, vals in DEFAULT_RISK_SETTINGS.items():
            for key, value in vals.items():
                entries[disease][key].delete(0, tk.END)
                entries[disease][key].insert(0, str(value))

    btns = ttk.Frame(outer)
    btns.pack(fill="x", pady=(8,0))
    ttk.Button(btns, text="初期値に戻す", command=reset_values).pack(side="left")
    ttk.Button(btns, text="保存", command=save_values).pack(side="right", padx=5)
    ttk.Button(btns, text="閉じる", command=win.destroy).pack(side="right")

    def update_region(event=None):
        canvas2.configure(scrollregion=canvas2.bbox("all"))
    inner.bind("<Configure>", update_region)


# ============================================================
# 病害リスク ＆ 備考生成ロジック（温暖地・環境最適化版）
# ============================================================
def get_risk_label(level):
    labels = {
        0: "安全0",
        1: "警戒1",
        2: "危険2",
        3: "危険3",
        4: "危険4",
        5: "危険5",
        6: "危険6",
    }
    return labels.get(level, "安全0")


def _float_list(text):
    return [float(x.strip()) for x in str(text).split(",") if x.strip()]


def evaluate_seasonal_disease_risk(
    avg_temp, max_temp, min_temp, avg_hum, precip,
    wet_hours_per_day=0.0, wet_hours_lt20_per_day=0.0,
    wet_hours_15_20_per_day=0.0, hot_hours_gt30_per_day=0.0,
):
    s = RISK_SETTINGS

    # 1. 黒点病：葉濡れを主軸
    q = s["black_spot"]
    if avg_temp < q["temp_min"] or avg_temp > q["temp_max"]:
        bs_level = 0
    else:
        if q["temp_opt_min"] <= avg_temp <= q["temp_opt_max"]:
            tf = 1.0
        elif q["temp_good_min"] <= avg_temp <= q["temp_good_max"]:
            tf = 0.75
        else:
            tf = 0.40
        t1,t2,t3,t4 = [q[k] for k in ("wet_t1","wet_t2","wet_t3","wet_t4")]
        ws = _float_list(q["wet_scores"])
        if len(ws) < 5: ws = [0,1,2,4,5]
        if wet_hours_per_day < t1: wet_score=ws[0]
        elif wet_hours_per_day < t2: wet_score=ws[1]
        elif wet_hours_per_day < t3: wet_score=ws[2]
        elif wet_hours_per_day < t4: wet_score=ws[3]
        else: wet_score=ws[4]
        raw = wet_score * tf
        if precip > q["rain_floor"] and wet_hours_per_day >= q["wet_floor"]:
            raw = max(raw, q["floor_score"])
        if (wet_hours_per_day >= q["long_wet_hours"] and
            q["long_wet_temp_min"] <= avg_temp <= q["long_wet_temp_max"]):
            raw = max(raw, q["long_wet_floor"])
        bs_level = max(0, min(6, int(round(raw))))

    def powdery(level_type):
        q = s[level_type]
        if avg_temp < q["temp_min"] or avg_temp > q["temp_max"]:
            return 0
        scores = _float_list(q["base_scores"])
        while len(scores) < 4: scores.append(scores[-1] if scores else 1)
        if q["best_min"] <= avg_temp <= q["best_max"]: base=scores[3]
        elif q["mid_min"] <= avg_temp <= q["mid_max"]: base=scores[2]
        elif q["low_min"] <= avg_temp <= q["low_max"]: base=scores[1]
        else: base=scores[0]
        h1,h2,h3,h4=[q[k] for k in ("hum_t1","hum_t2","hum_t3","hum_t4")]
        hf=_float_list(q["hum_factors"]); hf=(hf+[0]*5)[:5]
        if avg_hum < h1: factor=hf[0]
        elif avg_hum < h2: factor=hf[1]
        elif avg_hum < h3: factor=hf[2]
        elif avg_hum < h4: factor=hf[3]
        else: factor=hf[4]
        level=int(round(base*factor))
        if level_type == "powdery_open":
            r1,r2,r3=q["rain_t1"],q["rain_t2"],q["rain_t3"]
            rm=_float_list(q["rain_minus"]); rm=(rm+[0]*4)[:4]
            if precip <= r1: minus=rm[0]
            elif precip <= r2: minus=rm[1]
            elif precip <= r3: minus=rm[2]
            else: minus=rm[3]
            level -= int(round(minus))
        return max(0,min(6,level))

    pm_open_level = powdery("powdery_open")
    pm_roof_level = powdery("powdery_roof")

    # 4. べと病：平均気温だけでなく、20℃未満の濡れ時間と30℃超時間を反映
    q=s["downy"]
    if avg_temp < q["temp_min"] or avg_temp > q["temp_max"]:
        dm_level=0
    else:
        if q["opt_min"] <= avg_temp <= q["opt_max"]: tf=1.0
        elif q["good_min"] <= avg_temp <= q["good_max"]: tf=_float_list(q["temp_factors"])[1]
        else: tf=_float_list(q["temp_factors"])[0]
        h1,h2,h3,h4,h5=[q[k] for k in ("hum_t1","hum_t2","hum_t3","hum_t4","hum_t5")]
        hf=_float_list(q["hum_factors"]); hf=(hf+[0]*6)[:6]
        if avg_hum < h1: hfct=hf[0]
        elif avg_hum < h2: hfct=hf[1]
        elif avg_hum < h3: hfct=hf[2]
        elif avg_hum < h4: hfct=hf[3]
        elif avg_hum < h5: hfct=hf[4]
        else: hfct=hf[5]
        t1,t2,t3,t4=[q[k] for k in ("wet_t1","wet_t2","wet_t3","wet_t4")]
        wf=_float_list(q["wet_factors"]); wf=(wf+[0]*5)[:5]
        if wet_hours_lt20_per_day < t1: wfac=wf[0]
        elif wet_hours_lt20_per_day < t2: wfac=wf[1]
        elif wet_hours_lt20_per_day < t3: wfac=wf[2]
        elif wet_hours_lt20_per_day < t4: wfac=wf[3]
        else: wfac=wf[4]
        r1,r2,r3=q["rain_t1"],q["rain_t2"],q["rain_t3"]
        rf=_float_list(q["rain_factors"]); rf=(rf+[0]*4)[:4]
        if precip <= r1: rainfac=rf[0]
        elif precip <= r2: rainfac=rf[1]
        elif precip <= r3: rainfac=rf[2]
        else: rainfac=rf[3]
        raw=6*tf*hfct*wfac*rainfac
        # 15～20℃の実際の「濡れ候補時間」が少ない場合は過大評価を抑える
        if wet_hours_15_20_per_day < 0.5: raw *= 0.55
        elif wet_hours_15_20_per_day < 1.0: raw *= 0.75
        # 真夏の高温時間が多い旬は、べと病リスクを明確に下げる
        if hot_hours_gt30_per_day >= q["very_hot_hours"]: raw *= q["very_hot_factor"]
        elif hot_hours_gt30_per_day >= q["hot_reduction_hours"]: raw *= q["hot_factor"]
        if q["opt_min"] <= avg_temp <= q["opt_max"] and wet_hours_lt20_per_day >= q["min_wet_warning"] and avg_hum >= q["min_hum_warning"]:
            raw=max(raw,q["warning_floor"])
        if q["opt_min"] <= avg_temp <= q["opt_max"] and wet_hours_lt20_per_day >= q["min_wet_danger2"] and avg_hum >= q["min_hum_danger2"]:
            raw=max(raw,q["danger2_floor"])
        dm_level=max(0,min(6,int(round(raw))))

    # 5. さび病
    q=s["rust"]
    if avg_temp < q["temp_min"] or avg_temp > q["temp_max"]:
        rust_level=0
    else:
        if q["opt_min"] <= avg_temp <= q["opt_max"]: tf=1.0
        elif q["good_min"] <= avg_temp <= q["good_max"]: tf=0.75
        else: tf=0.40
        t1,t2,t3,t4=[q[k] for k in ("wet_t1","wet_t2","wet_t3","wet_t4")]
        ws=_float_list(q["wet_scores"]); ws=(ws+[0]*5)[:5]
        if wet_hours_per_day < t1: wscore=ws[0]
        elif wet_hours_per_day < t2: wscore=ws[1]
        elif wet_hours_per_day < t3: wscore=ws[2]
        elif wet_hours_per_day < t4: wscore=ws[3]
        else: wscore=ws[4]
        h1,h2,h3=[q[k] for k in ("hum_t1","hum_t2","hum_t3")]
        hf=_float_list(q["hum_factors"]); hf=(hf+[0]*4)[:4]
        if avg_hum < h1: hfac=hf[0]
        elif avg_hum < h2: hfac=hf[1]
        elif avg_hum < h3: hfac=hf[2]
        else: hfac=hf[3]
        raw=wscore*tf*hfac
        if precip > q["rain_bonus_threshold"]: raw += q["rain_bonus"]
        if q["floor_temp_min"] <= avg_temp <= q["floor_temp_max"] and wet_hours_per_day >= q["floor_wet_hours"] and avg_hum >= q["floor_hum"]:
            raw=max(raw,q["floor_score"])
        rust_level=max(0,min(6,int(round(raw))))

    notes=[]
    if (10 <= min_temp <= 18) and (18 <= max_temp <= 25) and avg_hum >= 75: notes.append("夜露・結露注意")
    elif (12 <= avg_temp <= 22) and avg_hum >= 80: notes.append("朝夕の多湿・露注意")
    if max_temp >= 32: notes.append("高温薬害・夏バテ注意")
    elif max_temp >= 29: notes.append("日中の薬害注意")
    if precip > 60 and avg_temp >= 20: notes.append("高温多湿（べと・黒点警戒）")
    elif 50 <= precip <= 60: notes.append("長雨による黒点多発")
    if wet_hours_per_day >= 6 and 15 <= avg_temp <= 27: notes.append(f"黒点病：葉濡れ推定{wet_hours_per_day:.1f}時間/日")
    if wet_hours_lt20_per_day >= 6 and 10 <= avg_temp <= 22: notes.append(f"べと病：20℃未満の葉濡れ推定{wet_hours_lt20_per_day:.1f}時間/日")
    if precip < 5 and avg_hum < 60: notes.append("乾燥注意（ハダニ等）")
    if max_temp < 12: notes.append("低温停滞期")
    return (get_risk_label(bs_level),get_risk_label(pm_open_level),get_risk_label(pm_roof_level),get_risk_label(dm_level),get_risk_label(rust_level)," / ".join(notes) if notes else "特記事項なし")


# ============================================================
# APIからデータ取得
# ============================================================
def fetch_historical_climate(lat, lon):
    try:
        start_year = datetime.now().year - 11
        end_year = datetime.now().year - 1

        start_date = f"{start_year}-01-01"
        end_date = f"{end_year}-12-31"

        # 日別データ：画面表示用の平年値
        # ERA5-Landを固定して、年によってモデルが変わらないようにする。
        daily_url = (
            f"https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={lat}&longitude={lon}"
            f"&start_date={start_date}&end_date={end_date}"
            f"&daily=temperature_2m_mean,temperature_2m_max,temperature_2m_min,"
            f"relative_humidity_2m_mean,precipitation_sum"
            f"&timezone=Asia%2FTokyo&models=era5_land"
        )

        # 時間別データ：べと病の葉濡れ条件推定用
        hourly_url = (
            f"https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={lat}&longitude={lon}"
            f"&start_date={start_date}&end_date={end_date}"
            f"&hourly=temperature_2m,relative_humidity_2m,precipitation"
            f"&timezone=Asia%2FTokyo&models=era5_land"
        )

        daily_res = requests.get(daily_url, timeout=30)
        daily_res.raise_for_status()
        daily_data = daily_res.json()

        if "daily" not in daily_data:
            return None, "日別気象データの取得に失敗しました。"

        hourly_res = requests.get(hourly_url, timeout=30)
        hourly_res.raise_for_status()
        hourly_data = hourly_res.json()

        if "hourly" not in hourly_data:
            return None, "時間別気象データの取得に失敗しました。"

        # APIが実際に採用した地点・標高・タイムゾーンを保存
        DATA_INFO.update({
            "requested_lat": lat, "requested_lon": lon,
            "data_lat": daily_data.get("latitude"),
            "data_lon": daily_data.get("longitude"),
            "elevation": daily_data.get("elevation"),
            "timezone": daily_data.get("timezone", "Asia/Tokyo"),
            "start_year": start_year, "end_year": end_year,
            "years": end_year - start_year + 1,
            "dataset": "ERA5-Land（長期比較向け）",
        })

        daily = daily_data["daily"]
        dates = daily["time"]
        t_means = daily["temperature_2m_mean"]
        t_maxs = daily["temperature_2m_max"]
        t_mins = daily["temperature_2m_min"]
        hums = daily["relative_humidity_2m_mean"]
        precips = daily["precipitation_sum"]

        # 旬別バケット
        seasonal_buckets = {
            (m, p): {
                "t_mean": [],
                "t_max": [],
                "t_min": [],
                "hum": [],
                "precip_sum_per_year": {
                    y: 0.0 for y in range(start_year, end_year + 1)
                },
                # べと病用：20℃未満で「葉濡れ」と推定できる時間
                "wet_hours": 0.0,
                "wet_hours_lt20": 0.0,
                "wet_hours_15_20": 0.0,
                "hot_hours_gt30": 0.0,
                "hour_count_days": set(),
            }
            for m in range(1, 13)
            for p in (1, 2, 3)
        }

        # 日別データ集計
        for i, d_str in enumerate(dates):
            dt = datetime.strptime(d_str, "%Y-%m-%d")
            m, day, y = dt.month, dt.day, dt.year
            p = 1 if day <= 10 else (2 if day <= 20 else 3)

            b = seasonal_buckets[(m, p)]

            if t_means[i] is not None:
                b["t_mean"].append(t_means[i])
            if t_maxs[i] is not None:
                b["t_max"].append(t_maxs[i])
            if t_mins[i] is not None:
                b["t_min"].append(t_mins[i])
            if hums[i] is not None:
                b["hum"].append(hums[i])
            if precips[i] is not None:
                b["precip_sum_per_year"][y] += precips[i]

        # 時間別データから「葉濡れ推定時間」を作る。
        # 実測センサーではないため、RH>=90% または降水がある時間を
        # 葉濡れ候補とする。病害ごとに温度帯を変えて利用する。
        hourly = hourly_data["hourly"]
        h_times = hourly["time"]
        h_temps = hourly["temperature_2m"]
        h_hums = hourly["relative_humidity_2m"]
        h_precips = hourly["precipitation"]

        for i, dt_str in enumerate(h_times):
            # ISO形式の末尾を取り除いて日時化
            dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M")
            m, day = dt.month, dt.day
            p = 1 if day <= 10 else (2 if day <= 20 else 3)
            b = seasonal_buckets[(m, p)]

            b["hour_count_days"].add(dt.date())

            temp = h_temps[i]
            hum = h_hums[i]
            rain = h_precips[i]

            if temp is None:
                continue

            is_wet = (
                (hum is not None and hum >= 90)
                or (rain is not None and rain > 0.1)
            )

            if is_wet and 10 <= temp <= 30:
                b["wet_hours"] += 1.0

            if is_wet and temp < 20:
                b["wet_hours_lt20"] += 1.0
            if is_wet and 15 <= temp <= 20:
                b["wet_hours_15_20"] += 1.0
            if temp > 30:
                b["hot_hours_gt30"] += 1.0

        result_rows = []
        period_names = {1: "上旬", 2: "中旬", 3: "下旬"}

        for m in range(1, 13):
            for p in (1, 2, 3):
                b = seasonal_buckets[(m, p)]

                avg_temp = (
                    sum(b["t_mean"]) / len(b["t_mean"]) if b["t_mean"] else 0.0
                )
                avg_max = (
                    sum(b["t_max"]) / len(b["t_max"]) if b["t_max"] else 0.0
                )
                avg_min = (
                    sum(b["t_min"]) / len(b["t_min"]) if b["t_min"] else 0.0
                )
                avg_hum = (
                    sum(b["hum"]) / len(b["hum"]) if b["hum"] else 0.0
                )

                yearly_precips = list(b["precip_sum_per_year"].values())
                avg_precip = (
                    sum(yearly_precips) / len(yearly_precips)
                    if yearly_precips
                    else 0.0
                )

                day_count = len(b["hour_count_days"])
                wet_hours_per_day = (
                    b["wet_hours"] / day_count
                    if day_count
                    else 0.0
                )
                wet_hours_lt20_per_day = (
                    b["wet_hours_lt20"] / day_count
                    if day_count
                    else 0.0
                )
                wet_hours_15_20_per_day = (
                    b["wet_hours_15_20"] / day_count
                    if day_count
                    else 0.0
                )
                hot_hours_gt30_per_day = (
                    b["hot_hours_gt30"] / day_count
                    if day_count
                    else 0.0
                )

                bs, pm_o, pm_r, dm, rust, note = evaluate_seasonal_disease_risk(
                    avg_temp,
                    avg_max,
                    avg_min,
                    avg_hum,
                    avg_precip,
                    wet_hours_per_day,
                    wet_hours_lt20_per_day,
                    wet_hours_15_20_per_day,
                    hot_hours_gt30_per_day,
                )

                row = [
                    f"{m}月{period_names[p]}",
                    f"{avg_temp:.1f}℃",
                    f"{avg_max:.1f}℃",
                    f"{avg_min:.1f}℃",
                    f"{avg_hum:.0f}%",
                    f"{avg_precip:.1f}mm",
                    bs,
                    pm_o,
                    pm_r,
                    dm,
                    rust,
                    note,
                ]

                result_rows.append(row)

        return result_rows, None

    except Exception as e:
        return None, f"エラーが発生しました: {e}"


# ============================================================
# GUI / UI構成
# ============================================================
COL_WIDTHS = [85, 65, 65, 65, 55, 65, 75, 85, 85, 75, 75, 600]
HEADERS = [
    "時期",
    "平均気温",
    "最高気温",
    "最低気温",
    "湿度",
    "降水量",
    "黒点病",
    "うどんこ露地",
    "うどんこ軒下",
    "べと病",
    "さび病",
    "備考・注意事項",
]


def get_cell_bg(col_idx, val):
    val_str = str(val)
    if 6 <= col_idx <= 10:
        if "危険6" in val_str or "危険5" in val_str:
            return "#FFCDD2"
        elif "危険4" in val_str or "危険3" in val_str:
            return "#FFE082"
        elif "危険2" in val_str or "警戒1" in val_str:
            return "#FFF9C4"
    return "#FFFFFF"


def create_cell(
    parent, text, width, bg="#FFFFFF", font=("メイリオ", 8), anchor="center"
):
    f = tk.Frame(parent, width=width, height=24, bg=bg)
    f.pack_propagate(False)

    lbl = tk.Label(f, text=text, font=font, bg=bg, anchor=anchor)
    lbl.pack(fill="both", expand=True, padx=2)

    tk.Frame(f, width=1, bg="#CCCCCC").pack(side="right", fill="y")
    tk.Frame(f, height=1, bg="#CCCCCC").pack(side="bottom", fill="x")
    return f


def execute_analysis(event=None):
    raw_lat = unicodedata.normalize("NFKC", lat_entry.get()).strip()
    raw_lon = unicodedata.normalize("NFKC", lon_entry.get()).strip()

    try:
        lat = float(raw_lat)
        lon = float(raw_lon)
    except ValueError:
        messagebox.showwarning(
            "入力エラー", "緯度と経度には正しく半角数字を入力してください。"
        )
        return

    save_config(lat, lon)

    btn_search.config(state="disabled", text="過去気候データ取得・集計中...")
    root.update()

    rows, error = fetch_historical_climate(lat, lon)

    btn_search.config(state="normal", text="年間旬別病害リスクを集計・診断")

    if error:
        messagebox.showerror("エラー", error)
        return

    for widget in scroll_frame.winfo_children():
        widget.destroy()

    update_data_info_label()

    for row in rows:
        rf = tk.Frame(scroll_frame, bg="#FFFFFF")
        rf.pack(fill="x")
        for c, val in enumerate(row):
            anchor_pos = "w" if c == 11 else "center"
            create_cell(
                rf,
                val,
                COL_WIDTHS[c],
                bg=get_cell_bg(c, val),
                anchor=anchor_pos,
            ).pack(side="left")


# ============================================================
# GUIメイン画面構造
# ============================================================
root = tk.Tk()
root.title("バラ年間旬別 過去11年平均気象データ ＆ 5大病害リスク総合診断（判定数値変更対応版）")
root.geometry("1650x820")

input_frame = ttk.LabelFrame(root, text=" 座標設定 ", padding=10)
input_frame.pack(fill="x", padx=10, pady=5)

ttk.Label(input_frame, text="緯度:").pack(side="left", padx=(5, 2))
lat_entry = ttk.Entry(input_frame, width=12)
lat_entry.pack(side="left", padx=5)
lat_entry.bind("<Button-3>", show_context_menu)

ttk.Label(input_frame, text="経度:").pack(side="left", padx=(10, 2))
lon_entry = ttk.Entry(input_frame, width=12)
lon_entry.pack(side="left", padx=5)
lon_entry.bind("<Button-3>", show_context_menu)

btn_search = ttk.Button(
    input_frame, text="年間旬別病害リスクを集計・診断", command=execute_analysis
)
btn_search.pack(side="left", padx=15)

btn_criteria = ttk.Button(
    input_frame, text="判定基準を見る", command=open_criteria_window
)
btn_criteria.pack(side="left", padx=10)

btn_settings = ttk.Button(
    input_frame, text="判定数値を変更", command=open_risk_settings_window
)
btn_settings.pack(side="left", padx=5)

cfg = load_config()
if cfg.get("lat"):
    lat_entry.insert(0, cfg["lat"])
if cfg.get("lon"):
    lon_entry.insert(0, cfg["lon"])

info_frame = ttk.LabelFrame(root, text=" 取得データ・集計条件 ", padding=6)
info_frame.pack(fill="x", padx=10, pady=(0, 3))

info_label = ttk.Label(info_frame, text="まだ気象データを取得していません。緯度・経度を入力して診断してください。", justify="left")
info_label.pack(anchor="w")


def update_data_info_label():
    req_lat = DATA_INFO.get("requested_lat")
    req_lon = DATA_INFO.get("requested_lon")
    data_lat = DATA_INFO.get("data_lat")
    data_lon = DATA_INFO.get("data_lon")
    elev = DATA_INFO.get("elevation")
    start_year = DATA_INFO.get("start_year")
    end_year = DATA_INFO.get("end_year")
    years = DATA_INFO.get("years")
    tz = DATA_INFO.get("timezone", "Asia/Tokyo")
    dataset = DATA_INFO.get("dataset", "ERA5-Land")

    if req_lat is None:
        return

    location_text = f"指定座標：北緯 {req_lat:.4f} / 東経 {req_lon:.4f}"
    if data_lat is not None and data_lon is not None:
        location_text += f"　｜ データ取得グリッド中心：約 {data_lat:.4f}, {data_lon:.4f}"
    if elev is not None:
        location_text += f"　｜ 標高：約 {elev:.0f}m"

    period_text = f"対象期間：{start_year}～{end_year}年（{years}年間）"
    detail_text = (
        f"データ：Open-Meteo Historical Weather API / {dataset}　｜ "
        f"時間帯：{tz}　｜ "
        "旬別（上旬・中旬・下旬）に集計"
    )
    explanation = (
        "これは天気予報ではなく、指定座標付近の過去気象を平均した『旬別の平年傾向』です。 "
        "気温・湿度・降水量は対象期間の旬別平均、病害判定には時間別データから推定した葉濡れ時間も使用します。"
    )
    info_label.config(text=location_text + "\n" + period_text + "　｜　" + detail_text + "\n" + explanation)


table_frame = ttk.LabelFrame(
    root, text=" 旬別（上旬・中旬・下旬）詳細気象 ＆ リスク・備考一覧（過去11年平均） ", padding=5
)
table_frame.pack(fill="both", expand=True, padx=10, pady=5)

canvas = tk.Canvas(table_frame, bg="#FFFFFF", highlightthickness=0)
v_bar = ttk.Scrollbar(table_frame, orient="vertical", command=canvas.yview)
h_bar = ttk.Scrollbar(table_frame, orient="horizontal", command=canvas.xview)

canvas.configure(yscrollcommand=v_bar.set, xscrollcommand=h_bar.set)

v_bar.pack(side="right", fill="y")
h_bar.pack(side="bottom", fill="x")
canvas.pack(side="left", fill="both", expand=True)

container = tk.Frame(canvas, bg="#FFFFFF")
canvas.create_window((0, 0), window=container, anchor="nw")

header_frame = tk.Frame(container, bg="#FFFFFF")
header_frame.pack(fill="x", side="top")

for h, w in zip(HEADERS, COL_WIDTHS):
    create_cell(
        header_frame, h, w, bg="#D6EAF8", font=("メイリオ", 8, "bold")
    ).pack(side="left")

scroll_frame = tk.Frame(container, bg="#FFFFFF")
scroll_frame.pack(fill="x", side="top")


def update_scroll_region(e):
    canvas.configure(scrollregion=canvas.bbox("all"))


container.bind("<Configure>", update_scroll_region)

root.mainloop()
