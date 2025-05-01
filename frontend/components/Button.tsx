export default function Button(
  { children, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement>,
) {
  return (
    <button
      {...rest}
      className={`
        inline-flex w-full items-center justify-center gap-2
        rounded-lg bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500
        px-4 py-2 text-sm font-semibold tracking-wide text-white shadow-lg
        transition active:scale-95 hover:opacity-90
        focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-400
        disabled:opacity-50
      `}
    >
      {children}
    </button>
  );
}
