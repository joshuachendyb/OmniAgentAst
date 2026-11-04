// 编辑历史: 2026-10-05 小欧 - 新建: step 渲染显示偏好取值 hook(文档[9] 方案设计 §5.2)
//   唯一真源=后端 YAML(只读 getGroup('appearance')), 无 localStorage, 无第二真源
//   为何不用现成件: ①settingsApi.getGroup 是全量查询, 本 hook 只读两个键, 不该借道拿大对象;
//            ②useSettings 是设置页专用状态机(脏值草稿 + mtime 守卫 + beforeunload 拦截 + 全局 loading),
//              整包搬到 chat 页不成比例;
//            ③useSettings 的 localStorage 偏好层(PREF_KEY, 仍服务 appearance.fontSize/density)在跑,
//              但其白名单**不含**本两个键; 新键若走该层会指向 registry 里不存在的键, 故一律不走 — 小欧-2026-10-05
//   消费方: PipelineRenderer 顶层调一次, 经 props 各下其位(禁在 segs.map 回调内调 hook, 违 Rules of Hooks):
//           thoughtMarkdown→TextStream(markdown), reasoningVisible→ThinkingStream(defaultExpanded) — 小欧-2026-10-05
// 编辑历史: 2026-10-05 小欧 - 第2轮会审: 读取失败改为沿用上次成功值(原置全关且不重试, 收起=内容不可见); 删ready残留 — 小欧-2026-10-05
import { useEffect, useState } from 'react';
import { settingsApi } from '@/services/api/settings.api';
import { SETTINGS_SAVED_EVT } from '@/constants/settingsEvents';

// 与 registry 键名同源(后端 settings_registry.py appearance 组同名键为唯一定义点;
//   本处为前端镜像点, 改键必须两处同步 —— 前端无法直接消费后端 schema 的键名常量)
const KEY_MD = 'appearance.step_render.thoughtMarkdown';
const KEY_RV = 'appearance.step_render.reasoningVisible';

/** 渲染偏好的当前值; 缺键由后端按 registry 默认值回填(实测 get_group 走 _get_dotted 默认值分支) */
export interface StepRenderPrefs {
  /** 设置页标签「思考排版」: thought 块(TextStream)正文是否按 Markdown 语法渲染。
   *  不管 reasoning 块 —— 那是「推理内容」的事, 两个开关各自独立 */
  thoughtMarkdown: boolean;
  /** 设置页标签「推理内容」: reasoning 块(ThinkingStream)折叠态的初值,
   *  只作每段新思考的初始态; 每段思考可自行折叠/展开(独立 state, 不写回设置);
   *  语义=**默认值**: 设置值变化时由 ThinkingStream 的跟随逻辑纠正已渲染段,
   *  此时用户先前的临时折叠会被重置(设置一改即新基线, 见 ThinkingStream 的 touched 说明) */
  reasoningVisible: boolean;
}

export const useStepRenderPrefs = (): StepRenderPrefs => {
  const [prefs, setPrefs] = useState<StepRenderPrefs>({
    thoughtMarkdown: true,
    reasoningVisible: true,
  });

  // 2026-10-05 小欧 KISS-DIRECT: 生命周期不再藏进 useCallback(此前 reload 返回 cleanup 交给
  //   useEffect 当清理用, 绕了一层); 改为单个 effect 内定义 load + 订阅, 读一次真值 — 小欧-2026-10-05
  useEffect(() => {
    let alive = true;
    const load = () => {
      settingsApi
        .getGroup('appearance')
        .then(({ data }) => {
          if (!alive) return;
          setPrefs({
            thoughtMarkdown: Boolean(data[KEY_MD]),
            reasoningVisible: Boolean(data[KEY_RV]),
          });
        })
        .catch(() => {
          // 2026-10-05 小欧 第2轮会审修复: 原实现失败即置 {false,false} 且不重试, 一次网络抖动就让
          //   「推理内容」永久收起 —— 而"收起"是**内容不可见**(不是无害降级), 且改动前本组件
          //   完全不依赖网络, 属本次新引入的失败模式。现改为: 保持上一次成功值(首次失败则用默认值
          //   全开), 并在控制台留痕(渲染偏好非阻断项, 不弹 toast 打扰用户)。
          if (!alive) return;
          console.warn(
            '[useStepRenderPrefs] 读取 appearance 组设置失败, 沿用上一次成功值'
          );
        });
    };
    load();
    window.addEventListener(SETTINGS_SAVED_EVT, load);
    return () => {
      alive = false;
      window.removeEventListener(SETTINGS_SAVED_EVT, load);
    };
  }, []);

  return prefs;
};
