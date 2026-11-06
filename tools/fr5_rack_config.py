# FR5 받침 과제 — GR00T N1.7 NEW_EMBODIMENT 모달리티 설정 (fr5_to_gr00t.py 가 만든 meta/modality.json 과 짝)
#   state  eef[0:9] = x y z(m) + rot6d(회전행렬 첫 두 행) · gripper[9:11] = [g, -g]
#   action eef[0:9] = 다음 프레임 x y z + rot6d(현재 자세 기준 상대로 학습: R_ref^T(p−p_ref), R_ref^T R)
#          gripper[9:10] = 다음 프레임 g(절대)
#   video  agentview(3인칭) · wrist(손목), 지금 프레임 하나
from gr00t.configs.data.embodiment_configs import register_modality_config
from gr00t.data.embodiment_tags import EmbodimentTag
from gr00t.data.types import ActionConfig, ActionFormat, ActionRepresentation, ActionType, ModalityConfig

HORIZON = 16  # 한 번에 내는 행동 수(10 Hz 에서 1.6 s) — Isaac-GR00T 예제 값

fr5_rack_config = {
    "video": ModalityConfig(delta_indices=[0], modality_keys=["agentview", "wrist"]),
    "state": ModalityConfig(delta_indices=[0], modality_keys=["eef", "gripper"]),
    "action": ModalityConfig(
        delta_indices=list(range(HORIZON)),
        modality_keys=["eef", "gripper"],
        action_configs=[
            ActionConfig(rep=ActionRepresentation.RELATIVE, type=ActionType.EEF, format=ActionFormat.XYZ_ROT6D),
            ActionConfig(rep=ActionRepresentation.ABSOLUTE, type=ActionType.NON_EEF, format=ActionFormat.DEFAULT),
        ],
    ),
    "language": ModalityConfig(delta_indices=[0], modality_keys=["annotation.human.task_description"]),
}

register_modality_config(fr5_rack_config, embodiment_tag=EmbodimentTag.NEW_EMBODIMENT)
