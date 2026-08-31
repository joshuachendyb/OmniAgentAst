// 编辑历史: 2026-08-27 小欧 - 修复ctx-3: 保存失败/异步进行中必须preventDefault阻止卸载, 杜绝静默丢失
import { useEffect, useRef } from 'react';

export interface BeforeUnloadOptions {
  shouldSave: boolean;
  saveData: () => void | Promise<void>;
  showDialog?: boolean;
  dialogMessage?: string;
}

export const useBeforeUnload = (options: BeforeUnloadOptions) => {
  const {
    shouldSave,
    saveData,
    showDialog = false,
    dialogMessage = '您有未保存的更改，确定要离开吗？',
  } = options;

  const saveDataRef = useRef(saveData);
  saveDataRef.current = saveData;

  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (!shouldSave) return;

      let saveFailed = false;
      try {
        const result = saveDataRef.current();

        // 2026-08-27 小欧 修复ctx-3: 异步保存无法同步确认成败, 为防数据丢失直接阻止卸载
        if (result instanceof Promise) {
          e.preventDefault();
          e.returnValue = dialogMessage;
          result.catch((error) => {
            console.error('[beforeunload] 保存失败:', error);
          });
          return;
        }
      } catch (error) {
        // 2026-08-27 小欧 修复ctx-3: 同步保存异常 -> 阻止卸载, 不再静默放行
        console.error('[beforeunload] 保存异常:', error);
        saveFailed = true;
      }

      if (saveFailed) {
        e.preventDefault();
        e.returnValue = '数据保存失败，确定要离开吗？';
        return;
      }

      if (showDialog) {
        e.preventDefault();
        e.returnValue = dialogMessage;
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [shouldSave, showDialog, dialogMessage]);
};
