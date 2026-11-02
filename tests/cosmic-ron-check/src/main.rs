//! Validate generated COSMIC theme files: every path given must deserialize
//! into cosmic_theme::ThemeBuilder and build into a Theme.

use cosmic_theme::ThemeBuilder;

fn main() {
    let mut failed = 0;
    for path in std::env::args().skip(1) {
        let text = std::fs::read_to_string(&path).expect("read theme file");
        match ron::de::from_str::<ThemeBuilder>(&text) {
            Ok(builder) => {
                let dark = builder.palette.is_dark();
                let _theme = builder.build();
                println!("ok    {path} (dark={dark})");
            }
            Err(err) => {
                failed += 1;
                println!("FAIL  {path}: {err}");
            }
        }
    }
    println!("cosmic ron check: {failed} failed");
    std::process::exit(if failed == 0 { 0 } else { 1 });
}
