// 编辑历史: 2026-08-26 小欧 - 8.12 实施: 附件多模态预留区, 上传随E1携带(暂缓)(4.6.2)
// 编辑历史: 2026-08-28 小欧 - ①D/d2: 暂缓期隐藏不占位, 启用加 Tooltip 说明
// 编辑历史: 2026-10-06 小欧 - 北京老陈指令: 暂缓期不再隐藏, 改为显示+置灰(disabled)。
//   上传功能仍暂缓（beforeUpload 照旧拦），按钮置灰仅作占位预告，避免用户以为没这个功能。— 小欧-2026-10-06
/**
 * AttachmentArea - 附件/多模态预留区（当前可空实现）
 * 【小欧 2026-08-26 8.12】4.6.2 预留渲染与上传位；上传随 E1 请求内容携带（暂缓）
 * @author 小欧 @date 2026-08-26
 */
import React from 'react';
import { Button, Tooltip, Upload } from 'antd';
import { PaperClipOutlined } from '@ant-design/icons';

const AttachmentArea: React.FC<{ visible?: boolean; disabled?: boolean }> = ({
  visible = false,
  disabled = false,
}) => {
  if (!visible) return null;
  return (
    <Tooltip
      title={
        disabled
          ? '附件上传暂未启用（多模态预留）'
          : '支持图片/文件（多模态预留）'
      }
    >
      <Upload
        beforeUpload={() => false}
        showUploadList={false}
        disabled={disabled}
      >
        <Button size="small" icon={<PaperClipOutlined />} disabled={disabled}>
          附件
        </Button>
      </Upload>
    </Tooltip>
  );
};

export { AttachmentArea };
