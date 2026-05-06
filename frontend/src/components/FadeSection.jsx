import useFadeIn from "../hooks/useFadeIn";

export default function FadeSection({ children, className = "", as: As = "section", ...rest }) {
  const { ref, className: fadeCls } = useFadeIn();
  return (
    <As ref={ref} className={`${fadeCls} ${className}`} {...rest}>
      {children}
    </As>
  );
}
