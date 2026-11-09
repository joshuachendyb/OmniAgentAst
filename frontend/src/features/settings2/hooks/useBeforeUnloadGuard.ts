// 编辑历史: 2026-11-09 小欧 - 新建：未保存修改的离开拦截（原 useSettings 内联 effect 原样搬迁）— 小欧-2026-11-09
import { useEffect } from 'react';

// 离开守卫：存在未保存修改（设置项脏键/模型参数/③区草稿）时拦截刷新与关闭，对齐 chat 侧 useBeforeUnload 语义；
//   监听在 useEffect 内注册，dirtyKeys/model.isDirty/providerDraft 变化时自动重绑，无脏态时不拦截
export function useBeforeUnloadGuard(
  dirtyKeys: Record<string, boolean>,
  modelDirty: boolean,
  providerDraft: Record<string, unknown>
) {
  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (
        !Object.keys(dirtyKeys).length &&
        !modelDirty &&
        // 2026-09-27 小欧 - ③区草稿也算未保存修改（否则改了 base_url 直接刷新静默丢）- 小欧-2026-09-27
        !Object.keys(providerDraft).length
      )
        return;
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [dirtyKeys, modelDirty, providerDraft]);
}
