/**
 * Layout骨架屏组件
 * 
 * 功能：在Layout初始化完成前显示骨架屏
 * UI布局和视觉与现有Layout保持完全一致
 * 支持错误状态显示和重试按钮
 * 
 * @author 小资
 * @version 1.1.0
 * @since 2026-04-12
 * @update 2026-04-12 修正UI参数与Layout一致
 * @update 2026-04-12 添加错误状态和重试按钮支持
 */

import React from 'react';
import { Layout, Button } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import styles from './LayoutSkeleton.module.css';

const { Sider, Header, Content } = Layout;

/**
 * Layout骨架屏Props
 */
interface LayoutSkeletonProps {
  /** 是否显示移动端菜单骨架 */
  isMobile?: boolean;
  /** 错误信息 */
  error?: string;
  /** 重试回调 */
  onRetry?: () => void;
}

/**
 * Layout骨架屏组
 */
export const LayoutSkeleton: React.FC<LayoutSkeletonProps> = ({
  isMobile = false,
  error,
  onRetry,
}) => {
  return (
    <Layout className={styles.layoutSkeleton}>
      {!isMobile && (
        <Sider className={styles.skeletonSider}>
          <div className={styles.skeletonLogo}>
            <div className={styles.skeletonLogoAvatar} />
            <div className={styles.skeletonLogoText} />
          </div>
          <div className={styles.skeletonMenuItemActive} />
          <div className={styles.skeletonMenuItem} />
          <div className={styles.skeletonMenuItem} />
          <div className={styles.skeletonMenuItem} />
          <div className={styles.skeletonFooter} />
        </Sider>
      )}
      <Layout>
        <Header className={styles.skeletonHeader}>
          <div className={styles.skeletonHeaderTitle} />
          <div className={styles.skeletonHeaderTag} />
        </Header>
        <Content className={styles.skeletonContent}>
          {/* 错误状态显示 */}
          {error ? (
            <div className={styles.skeletonError}>
              <div className={styles.skeletonErrorIcon}>!</div>
              <div className={styles.skeletonErrorText}>{error}</div>
              {onRetry && (
                <Button 
                  type="primary" 
                  icon={<ReloadOutlined />} 
                  onClick={onRetry}
                  className={styles.skeletonRetryButton}
                >
                  重试
                </Button>
              )}
            </div>
          ) : (
            <div style={{ padding: '16px 24px' }} />
          )}
        </Content>
      </Layout>
    </Layout>
  );
};

export default LayoutSkeleton;