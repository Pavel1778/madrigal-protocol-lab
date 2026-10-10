// The UnoCSS output trips the lightningcss minifier shipped with this Vite
// version ("Invalid token in pseudo element"). Disabling CSS minification keeps
// the deck buildable; the file-size difference is irrelevant for a deck.
// A plain object avoids importing `vite`, which is only installed globally.
export default {
  // The Slidev CLI is installed globally, so Vite's default cache lives under
  // /usr/local and is not writable by the current user. Point it at the project.
  cacheDir: './.vite-cache',
  build: {
    cssMinify: false,
  },
}
