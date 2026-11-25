/**
 * The app's building blocks (Batch 10 A). Pages import from "ui" only; nothing here imports a
 * page. A component that wraps a third-party library does so in exactly one file, so replacing
 * the library touches only that file (none is wrapped yet: the date picker, dialogs, toasts and
 * menus are our own). Gallery: /dev/ui (development builds only).
 */
export { AlertBanner, FieldErrorList, type AlertBannerProps, type AlertTone } from "./AlertBanner";
export { Badge, CountBadge, type BadgeProps, type BadgeTone } from "./Badge";
export { Button, IconButton, type ButtonProps, type ButtonSize, type ButtonVariant, type IconButtonProps } from "./Button";
export { Calendar, type CalendarProps, type DayTone } from "./Calendar";
export { cn } from "./cn";
export { ConfirmDialog, canConfirm, type ConfirmDialogProps, type ConfirmOptions, type ConfirmVariant } from "./ConfirmDialog";
export { DatePicker, dateInputError, type DatePickerProps } from "./DatePicker";
export { DateRangePicker, type DateRangePickerProps, type DateRangePreset, type DateRangeValue } from "./DateRangePicker";
export * as dates from "./dates";
export { EmptyState, type EmptyStateProps } from "./EmptyState";
export {
  ApiError,
  describeError,
  ensureOk,
  fieldLabel,
  problemFromBody,
  problemFromResponse,
  type FieldError,
  type ProblemInfo,
} from "./errors";
export { Field, controlClass, type FieldProps } from "./Field";
export { LookupSelect, type LookupSelectProps } from "./LookupSelect";
export { Menu, type MenuAction, type MenuEntry, type MenuProps } from "./Menu";
export { Modal, type ModalProps, type ModalSize } from "./Modal";
export { NumberField, type NumberFieldProps } from "./NumberField";
export { PageHeader, type PageHeaderProps } from "./PageHeader";
export { Popover, type PopoverProps } from "./Popover";
export { ScrollArea, type ScrollAreaProps } from "./ScrollArea";
export { Select, type SelectOption, type SelectProps } from "./Select";
export { Skeleton, SkeletonTable, SkeletonText, type SkeletonProps } from "./Skeleton";
export { TabPanel, Tabs, tabPanelId, type TabItem, type TabsProps } from "./Tabs";
export { TextArea, TextField, type TextAreaProps, type TextFieldProps } from "./TextField";
export { Tooltip, type TooltipProps } from "./Tooltip";
export { UiProvider, useDialogs, useToast, type Dialogs, type Toasts } from "./UiProvider";
