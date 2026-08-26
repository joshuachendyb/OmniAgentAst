/**
 * AttachmentArea - 附件/多模态预留区（当前可空实现）
 * 【小欧 2026-08-26 8.12】4.6.2 预留渲染与上传位；上传随 E1 请求内容携带（暂缓）。
 * @author 小欧 @date 2026-08-26
 */
import React from 'react';
import { Button, Upload } from 'antd';
import { PaperClipOutlined } from '@ant-design/icons';

const AttachmentArea: React.FC = () => (
  <Upload beforeUpload={() => false} showUploadList={false} disabled>
    <Button size="small" icon={<PaperClipOutlined />} disabled>
      附件
    </Button>
  </Upload>
);

export { AttachmentArea };
