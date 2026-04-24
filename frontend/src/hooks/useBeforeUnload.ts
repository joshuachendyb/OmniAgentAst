import { useEffect, useCallback, useRef } from 'react';

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
    dialogMessage = '您有未保存的更改，确定要离开吗？'
  } = options;

  const saveDataRef = useRef(saveData);
  saveDataRef.current = saveData;

  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (!shouldSave) return;

      try {
        const result = saveDataRef.current();

        if (result instanceof Promise) {
          result.catch((error) => {
            console.error('[beforeunload] 保存失败:', error);
          });
        }

        if (showDialog) {
          e.preventDefault();
          e.returnValue = dialogMessage;
        }
      } catch (error) {
        console.error('[beforeunload] 保存异常:', error);
        if (showDialog) {
          e.preventDefault();
          e.returnValue = '数据保存失败，确定要离开吗？';
        }
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [shouldSave, showDialog, dialogMessage]);
};