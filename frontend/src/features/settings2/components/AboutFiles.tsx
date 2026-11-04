// AboutFiles.tsx — 关于区「查看配置文件 / 查看版本文件」全文弹框（只读，Modal）
// 编辑历史: 2026-09-21 小强 - 新建：关于区文件查看（配置文件全文 / version 文件全文，Modal 只读展示）
// 2026-09-21 小强 - 视觉对齐项目 tokens（FontSize/Colors/Spacing/settingsRadius），全 antd SVG 图标，
//   代码区等宽 CODE 字号 + VERTICAL 边框 + TERTIARY 底，不硬编码色值/字号（stepStyles 铁律）。
// 2026-09-21 小欧 - 实施：关于区按钮由横排改竖排+靠左对齐
// 2026-09-21 小欧 - 实施：文件查看 Modal 作品级 UI——Header/元信息条/行号正文/加载错误态/footer
// 2026-09-21 小欧 - 全文核查：错误横幅改 Colors.ERROR 系（ERROR_BG/ERROR_BORDER/ERROR），与文档"Colors.ERROR 系"一致（设计文档 v1.12）
// 2026-09-21 小欧 - 全文核查：展示弹窗宽散落 800 → settingsModalWidth.display 令牌收口（设计文档 v1.12 规范一）
// 2026-09-21 小欧 - 全文核查：标题图标 marginRight:8、只读 badge padding:6/borderRadius:4 → Spacing.MD/SM、Radius.SM 令牌（设计文档 v1.12 铁规）
// 2026-09-21 小欧 - 关于区排版修复：按钮从独立竖排块改为嵌入对应信息行右侧（排版修复）
// 2026-09-21 小强 - 按钮改名：查看配置文件/查看版本文件（去"全文"，北京老陈定）
// 2026-09-21 小强 - 弹框优化：标题与按钮统一去"全文"（单源 docName 派生，删 title/btnLabel/报错三处双写）；行号栏 sticky；复制失败走框内错误条；空文件占位；Modal 加 destroyOnHidden（北京老陈定）
// 2026-09-22 小欧 - DRY+魔数收口：lineHeight:1.7 两处重复 → CODE_LINE_HEIGHT 常量；行号栏 minWidth:48 → LINE_NO_MIN_WIDTH 命名常量 - 小欧-2026-09-22
// 2026-10-06 小欧 - 修 bug：行号与内容整体错位。根因=正文 <pre> whiteSpace:'pre-wrap' 折行，
//   而行号栏 <pre> 是 'pre' 不折行 → 长行占 2 个视觉行、行号栏仍 1 行，其后所有行号集体下偏。
//   改法=弃「两列并排 pre」改「每条逻辑行 = 一个 grid row(行号格+文本格)」：折行只长高本行、
//   行号恒在行顶，结构上不可能错位；两格样式收口为 GUTTER_CELL/CODE_CELL 模块常量(共享
//   fontSize/lineHeight/fontFamily，防两处各写一遍再漂移)；容器 overflowX:'hidden'+overflowY:'auto'
//   且文本格 overflowWrap:'anywhere' → 超长 token 折行，不出横向滚动条(北京老陈要求不加横滚)。
//   同步删正文 wordBreak:'normal'(与新方案冲突)；content 不再直接渲染，全走 lines 逐行渲染。 - 小欧-2026-10-06
// 2026-10-10 小欧 - 弹窗归一：Modal → SettingsModal 标准壳。只读弹窗语义（display=800 宽度档、
//   关闭语义 ignore——遮罩/ESC 不关闭、只能点按钮关）；壳只统一标准行为，业务排版与行号正文样式原样保留。
//   实测：宽 800 / 遮罩不关 / ESC 不关 / 点主键才关，符合设计。
// 2026-10-10 北京老陈裁定 - 【定案，后续勿再翻】：配置文件全文含 api_key 等敏感项**明文直出**属预期行为，
//   不做掩码、不做脱敏、不做折叠。本弹窗是「自己看自己配置」的运维自检入口，只在已登录的本机页面
//   手动打开、非 URL 可直达、无后台定时推送/分享链路，与「列表里给旁人看的字段」是两类不同场景。
//   （此前小欧按"通用安全直觉"把它列为 P0 提报，属误判，已撤回。）
//   ⚠ 后续任何人再以此理由建议加掩码，先读这条，按"已裁定"处理，不要重开讨论 — 小欧-2026-10-10
// 编辑历史: 2026-10-14 小欧 - 删本地 formatSize 改用公用 @/utils/format 的 formatBytes（DRY）。
//   可见变化: ≥10MB 的文件由 "1024.0 MB" 改显 "1.0 GB"（原单位封顶 MB，GB 级会显示成没法读的数字）；<10MB 不变。
// 编辑历史: 2026-10-22 小欧 - CODE_FONT 硬编码 'Consolas, Menlo, monospace' 收敛到 FontFamily.MONO 令牌(DRY) — 小欧-2026-10-22
import React, { useCallback, useMemo, useState } from 'react';
import { Button, Spin } from 'antd';
import { FileDoneOutlined, FileTextOutlined } from '@ant-design/icons';
import { configApi } from '@/services/api/config.api';
import { SettingsModal } from '@/theme/SettingsModal';
import {
  Colors,
  FontFamily,
  FontSize,
  FontWeight,
  Spacing,
} from '@/utils/stepStyles';
// 2026-10-10 22:15 小欧 - 随「只读」badge 删除，同步清 Radius_SM / settingsModalWidth 两个失效 import
import { settingsRadius } from '@/theme/settingsTokens';
import { showSuccess } from '@/services/error/handler';
import { CopyIcon } from './icons';
import { formatBytes } from '@/utils/format';

type FileKind = 'config' | 'version';

// 2026-10-22 小欧 - 字体栈收敛到 FontFamily.MONO 令牌(DRY: 原此处硬编码 'Consolas, Menlo, monospace',
//   与仓库令牌两套字形并存, 统一到令牌) — 小欧-2026-10-22
// 2026-09-22 小欧 - DRY 收口：行号栏/正文两处 lineHeight:1.7 → 单常量（杜绝改一处漏一处）
const CODE_LINE_HEIGHT = 1.7;
// 2026-09-22 小欧 - 魔数收口：行号栏固定最小宽 48 提取命名常量（代码区等宽布局固有值）
const LINE_NO_MIN_WIDTH = 48;

// 2026-10-06 小欧 - 行号格/文本格样式提为模块常量：同一逻辑行的两格必须共享 fontSize/lineHeight/fontFamily，
//   否则行高不一致会再次错位（DRY：杜绝两处各写一遍又漂移）。
const GUTTER_CELL: React.CSSProperties = {
  padding: `0 ${Spacing.MD}px`,
  background: Colors.BG.TERTIARY,
  color: Colors.TEXT.SECONDARY,
  textAlign: 'right',
  userSelect: 'none',
  fontSize: FontSize.CODE,
  lineHeight: CODE_LINE_HEIGHT,
  fontFamily: FontFamily.MONO,
  minWidth: LINE_NO_MIN_WIDTH,
  borderRight: `1px solid ${Colors.BORDER.VERTICAL}`,
};
const CODE_CELL: React.CSSProperties = {
  padding: `0 ${Spacing.XL}px`,
  background: Colors.BG.PRIMARY,
  color: Colors.TEXT.PRIMARY,
  fontSize: FontSize.CODE,
  lineHeight: CODE_LINE_HEIGHT,
  fontFamily: FontFamily.MONO,
  whiteSpace: 'pre-wrap',
  overflowWrap: 'anywhere',
};

const stripBom = (s: string): string => s.replace(/^\uFEFF/, '');

const btnStyle: React.CSSProperties = {
  fontSize: FontSize.PRIMARY,
  fontWeight: FontWeight.REGULAR,
};

interface FileMeta {
  path: string;
  size: number;
  lines: number;
  mtime: number;
}

const formatTime = (ts: number): string => {
  try {
    return new Date(ts * 1000).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return String(ts);
  }
};

interface AboutFilesProps {
  kind: FileKind;
}

export const AboutFiles: React.FC<AboutFilesProps> = ({ kind }) => {
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState('');
  const [meta, setMeta] = useState<FileMeta | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 2026-09-21 小强 - 单源 docName：标题/按钮/报错/toast/复制按钮全由它派生，删 title/btnLabel/报错三处双写（DRY）
  const docName = kind === 'config' ? '配置文件' : '版本文件';

  const openFile = useCallback(async () => {
    setLoading(true);
    setOpen(true);
    setError(null);
    setContent('');
    setMeta(null);
    try {
      if (kind === 'config') {
        const res = await configApi.readConfigFile();
        setContent(stripBom(res.config_content));
        setMeta({
          path: res.path,
          size: res.size,
          lines: res.lines,
          mtime: res.mtime,
        });
      } else {
        const res = await configApi.readVersionFile();
        setContent(stripBom(res.version_content));
        setMeta({
          path: res.path,
          size: res.size,
          lines: res.lines,
          mtime: res.mtime,
        });
      }
    } catch {
      setError('读取' + docName + '失败');
    } finally {
      setLoading(false);
    }
  }, [kind, docName]);

  const close = useCallback(() => {
    setOpen(false);
    setContent('');
    setMeta(null);
    setError(null);
  }, []);

  const copyAll = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(content);
      showSuccess(`已复制${docName}`);
    } catch {
      setError('复制失败，请手动选择复制');
    }
  }, [content, docName]);

  const lines = useMemo(() => content.split('\n'), [content]);
  const icon = kind === 'config' ? <FileTextOutlined /> : <FileDoneOutlined />;

  return (
    <>
      <Button icon={icon} style={btnStyle} loading={loading} onClick={openFile}>
        查看{docName}
      </Button>
      <SettingsModal
        open={open}
        width="display"
        closeBehavior="ignore"
        onCancel={close}
        // 2026-10-10 22:15 小欧 - 视觉优化（问题#15）：只读窗的**主动作是「复制」不是「关闭」——
        //   用户打开文件预览九成是为了拿走内容，原实现把蓝色主键给「关闭」，「复制」退化成灰键，
        //   主次颠倒。改为「复制」primary、「关闭」default。
        footer={[
          <Button
            key="copy"
            type="primary"
            icon={<CopyIcon />}
            onClick={copyAll}
            disabled={!content}
          >
            复制{docName}
          </Button>,
          <Button key="close" onClick={close}>
            关闭
          </Button>,
        ]}
        title={
          <div>
            <div
              style={{
                fontWeight: FontWeight.BOLD,
                fontSize: FontSize.PRIMARY,
              }}
            >
              <span style={{ marginRight: Spacing.MD }}>{icon}</span>
              {docName}
            </div>
            {meta && (
              <div
                style={{
                  fontSize: FontSize.SECONDARY,
                  color: Colors.TEXT.SECONDARY,
                  fontWeight: FontWeight.REGULAR,
                }}
              >
                {meta.path}
              </div>
            )}
          </div>
        }
      >
        {meta && (
          <div
            style={{
              display: 'flex',
              gap: Spacing.LG,
              alignItems: 'center',
              padding: `${Spacing.SM}px ${Spacing.MD}px`,
              background: Colors.BG.TERTIARY,
              borderRadius: settingsRadius.DEFAULT,
              marginBottom: Spacing.MD,
              fontSize: FontSize.SECONDARY,
              color: Colors.TEXT.SECONDARY,
            }}
          >
            <span>{meta.lines} 行</span>
            <span>·</span>
            <span>{formatBytes(meta.size)}</span>
            <span>·</span>
            <span>更新 {formatTime(meta.mtime)}</span>
            {/* 2026-10-10 22:15 小欧 - 视觉优化（问题#14/#16）：删「只读」badge（整窗就是只读的，
                右挂标签零信息量还占位）；补「共 N 行 · 可滚动」溢出提示（原 321 行内容被裁到
                ~20 行，底部无任何可滚动提示，用户以为文件就这么长）。 */}
            <span
              style={{
                marginLeft: 'auto',
                fontSize: FontSize.SMALL,
                color: Colors.TEXT.TERTIARY,
              }}
            >
              可滚动查看全部 {meta.lines} 行
            </span>
          </div>
        )}
        {loading && (
          <div style={{ textAlign: 'center', padding: Spacing.XL * 2 }}>
            <Spin tip="正在读取文件…" />
          </div>
        )}
        {error && (
          <div
            style={{
              padding: Spacing.MD,
              background: Colors.ERROR_BG,
              border: `1px solid ${Colors.ERROR_BORDER}`,
              borderRadius: settingsRadius.DEFAULT,
              color: Colors.ERROR,
              marginBottom: Spacing.MD,
            }}
          >
            {error}
          </div>
        )}
        {!loading && !error && content && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'auto 1fr',
              maxHeight: '60vh',
              overflowY: 'auto',
              overflowX: 'hidden',
              padding: `${Spacing.LG}px 0`,
              border: `1px solid ${Colors.BORDER.VERTICAL}`,
              borderRadius: settingsRadius.LG,
            }}
          >
            {lines.map((line, i) => (
              <React.Fragment key={i}>
                <div data-line-no={i + 1} style={GUTTER_CELL}>
                  {i + 1}
                </div>
                <div data-line-text={i + 1} style={CODE_CELL}>
                  {line}
                </div>
              </React.Fragment>
            ))}
          </div>
        )}
        {!loading && !error && !content && (
          <div
            style={{
              textAlign: 'center',
              padding: Spacing.XL * 2,
              color: Colors.TEXT.SECONDARY,
              fontSize: FontSize.SECONDARY,
            }}
          >
            文件为空
          </div>
        )}
      </SettingsModal>
    </>
  );
};
