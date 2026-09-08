#!/usr/bin/env python3
"""丰田 TSS2 原车跟车距离诊断工具（卡罗拉 TSS2 / COROLLA_TSS2）

用途：验证"方向盘车距按键 -> 原车 PCM 档位 -> openpilot 跟车时距"这条链路是否打通。

同时观察三路信号：
  1) PCM_CRUISE_2  (0x1D3) .PCM_FOLLOW_DISTANCE  原车档位，1=远 2=中 3=近（权威来源）
  2) PCM_CRUISE_SM (0x399) .DISTANCE_LINES       仪表车距显示，1=近 2=中 3=远
     注意方向与前一路相反，仅用于交叉验证：它变化说明 PCM 确实收到了按键
  3) carState.pcmFollowDistance -> controlsState.personality
     openpilot 的解析结果与映射后的驾驶风格

用法（ssh 进设备，openpilot 运行中）：
  cd /data/openpilot && python3 selfdrive/debug/pcm_distance_check.py

按方向盘车距键，三路信号应同步在 1/2/3 之间循环。
若 1) 2) 都不变：说明该年款 PCM 在 openpilot 接管纵向时不响应车距按键。
若 1) 2) 变但 3) 不变：说明解析/映射有问题，检查 carstate 是否写入 pcmFollowDistance。
"""

import time

import cereal.messaging as messaging
from cereal import car
from opendbc.can.parser import CANParser

from openpilot.common.params import Params
from openpilot.selfdrive.car.toyota.values import DBC

# 原车档位 -> 文字（PCM_FOLLOW_DISTANCE 定义：1=far 2=medium 3=close）
PCM_DISTANCE_TXT = {0: "无效/未初始化", 1: "1 远 far", 2: "2 中 medium", 3: "3 近 close"}
# 仪表车距显示（DISTANCE_LINES 定义：0=不显示 1=close 2=medium 3=far，方向相反）
DISTANCE_LINES_TXT = {0: "0 不显示", 1: "1 近", 2: "2 中", 3: "3 远"}
# LongitudinalPersonality 枚举：aggressive=0 standard=1 relaxed=2
PERSONALITY_TXT = {0: "aggressive 近 1.4s", 1: "standard 中 1.8s", 2: "relaxed 远 2.2s"}


def main():
  params = Params()
  CP = car.CarParams.from_bytes(params.get("CarParams", block=True))
  print(f"车型 fingerprint : {CP.carFingerprint}")
  print(f"openpilot 纵向控制: {CP.openpilotLongitudinalControl}")
  print(f"雷达不可用        : {CP.radarUnavailable}")
  print(f"DBC(pt)          : {DBC[CP.carFingerprint]['pt']}")
  print("-" * 72)

  # 在 powertrain bus(0) 上解析 PCM 广播的两路档位信号
  messages = [("PCM_CRUISE_2", 33), ("PCM_CRUISE_SM", 1)]
  cp = CANParser(DBC[CP.carFingerprint]["pt"], messages, 0)

  can_sock = messaging.sub_sock('can')
  sm = messaging.SubMaster(['carState', 'controlsState'])

  last_print = 0.0
  print(f"{'PCM档位':<16}{'仪表车距':<12}{'pcmFollowDistance':<20}{'personality':<24}{'巡航'}")
  while True:
    can_strs = messaging.drain_sock(can_sock, wait_for_one=False)
    if can_strs:
      cp.update_strings(can_strs)

    sm.update(0)

    now = time.monotonic()
    if now - last_print < 0.5:
      time.sleep(0.01)
      continue
    last_print = now

    # 1) 原车档位（权威来源）
    pcm_dist = 0
    if "PCM_CRUISE_2" in cp.vl and cp.vl["PCM_CRUISE_2"]:
      pcm_dist = int(cp.vl["PCM_CRUISE_2"].get("PCM_FOLLOW_DISTANCE", 0) or 0)

    # 2) 仪表显示（交叉验证）
    lines = -1
    if "PCM_CRUISE_SM" in cp.vl and cp.vl["PCM_CRUISE_SM"]:
      raw = cp.vl["PCM_CRUISE_SM"].get("DISTANCE_LINES")
      lines = int(raw) if raw is not None else -1

    # 3) openpilot 解析与映射结果
    cs = sm['carState']
    pfd = int(getattr(cs, 'pcmFollowDistance', 0)) if sm.updated['carState'] or sm.alive['carState'] else 0
    per = int(sm['controlsState'].personality)
    cruise = "ON" if cs.cruiseState.enabled else "off"

    print(f"{PCM_DISTANCE_TXT.get(pcm_dist, str(pcm_dist)):<16}"
          f"{DISTANCE_LINES_TXT.get(lines, str(lines)):<12}"
          f"{str(pfd):<20}"
          f"{PERSONALITY_TXT.get(per, str(per)):<24}"
          f"{cruise}")


if __name__ == "__main__":
  main()
