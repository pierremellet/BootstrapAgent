import Link from "next/link";

export default function Home() {
  return (
    <div className="flex items-center justify-center min-h-screen p-8">
      <Link
        href="/chat"
        className="rounded-full border border-solid border-black/[.08] dark:border-white/[.145] transition-colors flex items-center justify-center bg-foreground text-background gap-2 h-12 px-5 font-medium text-base hover:bg-[#f2f2f2] dark:hover:bg-[#1a1a1a] hover:text-white"
      >
        Go to Chat
      </Link>
    </div>
  );
}