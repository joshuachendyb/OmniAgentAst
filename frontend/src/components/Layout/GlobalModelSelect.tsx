/**
 * GlobalModelSelect - 顶栏全局模型(L1)选择器(App壳层插槽控件)
 *
 * 功能：
 * - 展示当前全局模型(modelList.current_model 优先, 降落 serviceStatus.model_ref 派生)
 * - 切换写全局配置(switchAndRefreshModel 唯一写链), 切换前登记 attemptedModel 供失败态弹窗联动
 * - 打开下拉框时刷新模型列表获取最新配置; 无模型时降级"暂无模型" Tag
 * - 框宽/弹层宽唯一可调点 = TOP_MODEL_SELECT_WIDTH(仅 minWidth 下限), 与会话级 ModelPicker 互不共享隔离
 *
 * @author 小欧
 * @date 2026-11-02
 */
// 编辑历史: 2026-11-02 小欧 - SRP拆分新建: 领域逻辑自AppLayout迁入(index.tsx 362~374/448~493/845~876), 逻辑零改动 - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 死字段删除: onSwitchAttempted不再传display_name(接收侧hook从不读该字段) - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 解钩: onSwitchAttempted prop与attemptedModel登记全删(消费方useValidationFeedback已废) - 小欧-2026-11-02
import React from 'react';
import { Select, Tag } from 'antd';
import { handleError, showSuccess, ErrorType } from '@/services/error/handler';
import { useApp } from '../../contexts/AppContext';

// 2026-11-02 小欧 - 顶部全局模型选择框宽度唯一可调点(仅作minWidth下限): 选中框+弹层两槽位共引, 改下限只改此一行; 与底部会话级ModelPicker常量互不共享隔离 — 小欧-2026-11-02
const TOP_MODEL_SELECT_WIDTH = 180;

const { Option } = Select;

export const GlobalModelSelect: React.FC = () => {
  const {
    modelList,
    serviceStatus,
    switchAndRefreshModel,
    refreshModelList: appRefreshModelList,
  } = useApp();

  // 【修复问题2】当前选中的模型ID（格式: provider-modelname）
  // 【2026-04-07修复】切换模型后不再调用refreshServiceStatus，所以必须优先从modelList获取
  const currentProvider = (() => {
    // 优先从 modelList 中找 current_model === true 的模型（切换模型后这里会更新）
    const currentModel = modelList.find((m) => m.current_model === true);
    if (currentModel) {
      return `${currentModel.provider}-${currentModel.model}`;
    }
    // 其次从 serviceStatus 获取（验证后的当前模型）— 归一: model_ref 结构派生 — 小欧 2026-08-22
    if (serviceStatus?.model_ref?.provider && serviceStatus?.model_ref?.model) {
      return `${serviceStatus.model_ref.provider}-${serviceStatus.model_ref.model}`;
    }
    // 如果都没有，返回空字符串
    return '';
  })();

  // 切换全局模型: 经AppContext.switchAndRefreshModel唯一写链, 失败只管展示(内部已刷新)
  const handleModelChange = async (value: string) => {
    try {
      const selectedModel = modelList.find(
        (m) => `${m.provider}-${m.model}` === value
      );
      if (!selectedModel) {
        handleError({
          message: '未找到对应的模型',
          error_type: ErrorType.LOAD_FAILED,
        });
        return;
      }
      // 归一(小欧 2026-08-22): ai_provider/ai_model → ai_model_ref 结构
      // 2026-09-24 小欧 - DRY收口: 改经switchAndRefreshModel(API+成功/失败刷新收口), 不再直调configApi+手动refreshAfterModelChange
      const result = await switchAndRefreshModel(
        selectedModel.provider,
        selectedModel.model
      );
      if (!result.success) {
        handleError({
          message: result.message || '切换失败',
          error_type: ErrorType.SWITCH_MODEL_FAILED,
        });
        // 切换失败时switchAndRefreshModel内部已刷新模型列表(后端回滚后状态), 此处只管展示
        return;
      }
      showSuccess(`已切换到 ${selectedModel.display_name}`);
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string } };
        message?: string;
      };
      console.error('[切换模型] 失败:', error);
      handleError({
        message: err?.response?.data?.detail || err?.message || '切换模型失败',
        error_type: ErrorType.SWITCH_MODEL_FAILED,
      });
    }
  };

  return (
    <>
      {modelList.length > 0 ? (
        <Select
          value={currentProvider}
          style={{ minWidth: TOP_MODEL_SELECT_WIDTH }}
          styles={{
            popup: { root: { minWidth: TOP_MODEL_SELECT_WIDTH } },
          }}
          size="small"
          // 2026-11-02 小欧 框宽下限+弹层下限共引TOP_MODEL_SELECT_WIDTH(改下限只改一行,与底部ModelPicker隔离); popupMatchSelectWidth=false 弹层仍自适应取最长选项 — 小欧-2026-11-02
          popupMatchSelectWidth={false}
          // 【新增】打开下拉框时刷新模型列表，获取最新配置
          onOpenChange={async (open: boolean) => {
            if (open) {
              await appRefreshModelList();
            }
          }}
          onChange={handleModelChange}
        >
          {modelList.map((model) => (
            <Option key={model.id} value={`${model.provider}-${model.model}`}>
              {model.current_model === true ? '★ ' : ''}
              {model.display_name}
            </Option>
          ))}
        </Select>
      ) : (
        <Tag color="warning">暂无模型</Tag>
      )}
    </>
  );
};
