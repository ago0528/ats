import { type CSSProperties, type ReactNode } from 'react';

import { Modal, type ModalProps } from 'antd';

type StandardModalStyles = NonNullable<ModalProps['styles']>;

const DEFAULT_MODAL_STYLES = {
  content: {
    height: 'fit-content',
    maxHeight: '80vh',
    display: 'flex',
    flexDirection: 'column' as const,
    overflow: 'hidden',
  },
  body: {
    padding: 0,
    overflowX: 'hidden',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column' as const,
    flex: 1,
    minHeight: 0,
  },
  footer: {
    display: 'flex',
    justifyContent: 'flex-end',
    alignItems: 'center',
    marginTop: '24px',
  },
};

type StandardModalProps = Omit<ModalProps, 'styles'> & {
  styles?: StandardModalStyles;
  bodyPadding?: CSSProperties['padding'];
  contentHeight?: CSSProperties['height'] | CSSProperties['maxHeight'];
};

export function StandardModal({
  styles,
  bodyPadding,
  contentHeight,
  okText = '저장',
  cancelText = '취소',
  ...props
}: StandardModalProps) {
  const mergedStyles: StandardModalStyles = {
    ...DEFAULT_MODAL_STYLES,
    ...styles,
    content: {
      ...DEFAULT_MODAL_STYLES.content,
      ...(styles?.content || {}),
      ...(contentHeight ? { maxHeight: contentHeight } : {}),
    },
    body: {
      ...DEFAULT_MODAL_STYLES.body,
      ...(styles?.body || {}),
      ...(bodyPadding !== undefined ? { padding: bodyPadding } : {}),
    },
  };

  return (
    <Modal
      {...props}
      okText={okText}
      cancelText={cancelText}
      styles={mergedStyles}
      destroyOnHidden={props.destroyOnHidden ?? true}
    />
  );
}

export function StandardModalMetaBlock({
  title,
  children,
  marginBottom = 12,
  padding = 0,
  gap = 8,
  alignItems,
}: {
  title?: ReactNode;
  children: ReactNode;
  marginBottom?: number;
  padding?: number;
  gap?: number;
  alignItems?: 'flex-start' | 'flex-end' | 'center';
}) {
  return (
    <div
      style={{
        fontSize: '14px',
        padding,
        marginBottom,
        display: 'flex',
        flexDirection: 'column',
        gap,
        alignItems,
      }}
    >
      {title ? <div>{title}</div> : null}
      {children}
    </div>
  );
}
