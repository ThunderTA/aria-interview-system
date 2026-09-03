import useInView from "../hooks/useInView";

/** Fades and lifts its children in once they scroll into view. */
export default function Reveal({ as: Tag = "div", className = "", delay = 0, children }) {
  const [ref, inView] = useInView();

  return (
    <Tag
      ref={ref}
      className={`reveal${inView ? " reveal--visible" : ""}${className ? ` ${className}` : ""}`}
      style={{ transitionDelay: inView ? `${delay}ms` : "0ms" }}
    >
      {children}
    </Tag>
  );
}
