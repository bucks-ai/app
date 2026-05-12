export function Footer() {
  return (
    <footer className="border-t border-white/10 bg-black px-6 py-10">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 text-sm text-neutral-500 sm:flex-row">
        <span>
          © {new Date().getFullYear()} bucks.ai — All rights reserved.
        </span>
        <span>Built for founders who ship.</span>
      </div>
    </footer>
  );
}
