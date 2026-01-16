"""Rose pine theme generator for notepad++."""

import logging
import subprocess
from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from enum import StrEnum
from xml.etree import ElementTree as ET

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Style:
    """Model for style."""

    names: list[str]
    fgColor: str | None = None
    bgColor: str | None = None

    def __post_init__(self):
        """Validate inputs."""
        if not self.names:
            raise ValueError("names list cannot be empty")
        if self.fgColor is None and self.bgColor is None:
            raise ValueError("At least one of fgColor or bgColor must be provided")
        if self.fgColor and self.fgColor.startswith("$") is False:
            raise ValueError("fgColor must start with '$' if provided")
        if self.bgColor and self.bgColor.startswith("$") is False:
            raise ValueError("bgColor must start with '$' if provided")

        self.names = sorted(set(self.names))


def update_fg_bg_color(
    element: ET.Element,
    style_name: str,
    new_fg_color: str | None = None,
    new_bg_color: str | None = None,
) -> ET.Element:
    """Update foreground and background colors.

    :param element: xml style element
    :type element: ET.Element
    :param style_name: style name to update color
    :type style_name: str
    :param new_fg_color: new foreground color, defaults to None
    :type new_fg_color: str | None, optional
    :param new_bg_color: new background color, defaults to None
    :type new_bg_color: str | None, optional
    :return: updated style element with new colors
    :rtype: ET.Element
    """
    if element.get("name") == style_name:
        if new_fg_color is not None:
            element.set("fgColor", new_fg_color)
        if new_bg_color is not None:
            element.set("bgColor", new_bg_color)
    else:
        logger.warning(
            f"Style name mismatch: expected `{style_name}` but got "
            f"`{element.get('name')}`."
        )
    return element


def parse_xml_file(file_path: str) -> ET.Element:
    """Parse xml file and return root.

    :param file_path: path of xml file
    :type file_path: str
    :return: root of xml file
    :rtype: ET.Element
    """
    tree = ET.parse(file_path)  # noqa: S314
    root = tree.getroot()
    return root


def get_lexer_styles(root: ET.Element) -> ET.Element:
    """Get lexer styles from source xml root.

    :param root: xml root element.
    :type root: ET.Element
    :return: lexer styles xml element
    :rtype: ET.Element
    """
    lexer_styles = root.find("LexerStyles")
    if lexer_styles is not None:
        return lexer_styles
    raise ValueError("LexerStyles element not found")


def get_global_styles(root: ET.Element) -> ET.Element:
    """Get global styles form source xml root.

    :param root: xml root element
    :type root: ET.Element
    :return: global styles xml element
    :rtype: ET.Element
    """
    global_styles = root.find("GlobalStyles")
    if global_styles is not None:
        return global_styles
    raise ValueError("GlobalStyles element not found")


def get_lexer_types(lexer_styles: ET.Element) -> list[ET.Element]:
    """Get lexer types from lexer styles.

    :param lexer_styles: lexer styles xml element
    :type lexer_styles: ET.Element
    :return: lexer types xml element
    :rtype: list[ET.Element]
    """
    return lexer_styles.findall("LexerType")


def get_words_styles(lexer_type: ET.Element) -> list[ET.Element]:
    """Get words styles from lexer type.

    :param lexer_type: lexer type xml element
    :type lexer_type: ET.Element
    :return: words styles xml element
    :rtype: list[ET.Element]
    """
    return lexer_type.findall("WordsStyle")


def get_widget_styles(global_styles: ET.Element) -> list[ET.Element]:
    """Get widget styles from global styles.

    :param global_styles: global styles xml element
    :type global_styles: ET.Element
    :return: widget styles xml element
    :rtype: list[ET.Element]
    """
    return global_styles.findall("WidgetStyle")


def get_distinct_style_names(lexer_styles: ET.Element) -> list[str]:
    """Get distinct style names.

    :param lexer_styles: lexer styles xml element
    :type lexer_styles: ET.Element
    :return: list of distinct style names
    :rtype: list[str]
    """
    distinct_style_names = set()
    for lexer_type in get_lexer_types(lexer_styles):
        for style in lexer_type.findall("WordsStyle"):
            distinct_style_names.add(style.get("name"))
    return sorted(distinct_style_names)


def get_distinct_missing_style_names(
    lexer_styles: ET.Element,
    styles: list[Style],
) -> list[str]:
    """Get distinct missing style names from config compared to source file.

    :param lexer_styles: lexer styles xml element
    :type lexer_styles: ET.Element
    :param styles: styles
    :type styles: list[Style]
    :return: list of distinct missing style names
    :rtype: list[str]
    """
    existing_style_names = set(get_distinct_style_names(lexer_styles))
    config_style_names = set()
    for words_style_config in styles:
        for name in words_style_config.names:
            config_style_names.add(name)
    missing_names = existing_style_names - config_style_names

    return sorted(missing_names)


def load_styles_from_config(config_file_path: str) -> list[Style]:
    """Load styles from config.

    :param config_file_path: config file path
    :type config_file_path: str
    :return: styles
    :rtype: list[Style]
    """
    styles: list[Style] = []
    with open(config_file_path, encoding="utf-8") as config_file:
        config_data = yaml.safe_load(config_file)
        for data in config_data.get("styles", []):
            styles.append(
                Style(
                    names=data.get("names", []),
                    fgColor=data.get("fgColor"),
                    bgColor=data.get("bgColor"),
                )
            )
    return styles


def format_config_file(
    config_file_path: str,
    styles: list[Style],
) -> None:
    """Format and save config file.

    :param config_file_path: config file path
    :type config_file_path: str
    :param styles: styles
    :type styles: list[Style]
    """
    config_data = {"styles": [asdict(style) for style in styles]}
    with open(config_file_path, "w", encoding="utf-8") as config_file:
        yaml.dump(
            config_data,
            config_file,
            sort_keys=True,
            indent=2,
        )


def create_or_update_template(
    source_file_path: str,
    target_file_path: str,
    config_file_path: str,
) -> None:
    """Create or update template file from the source file.

    :param source_file_path: source file path
    :type source_file_path: str
    :param target_file_path: target file path
    :type target_file_path: str
    :param config_file_path: config file path
    :type config_file_path: str
    """
    styles = load_styles_from_config(config_file_path)

    # parse and update XML file
    root = parse_xml_file(source_file_path)

    # update lexer styles
    lexer_styles = get_lexer_styles(root)
    lexer_types = get_lexer_types(lexer_styles)
    for lexer_type in lexer_types:
        words_styles = get_words_styles(lexer_type)
        for words_style in words_styles:
            for style in styles:
                for name in style.names:
                    _ = update_fg_bg_color(
                        words_style,
                        name,
                        style.fgColor,
                        style.bgColor,
                    )

    # update global styles
    global_styles = get_global_styles(root)
    widget_styles = get_widget_styles(global_styles)
    for widget_style in widget_styles:
        for style in styles:
            for name in style.names:
                _ = update_fg_bg_color(
                    widget_style,
                    name,
                    style.fgColor,
                    style.bgColor,
                )

    # write updated XML to target file
    tree = ET.ElementTree(root)
    tree.write(
        target_file_path,
        encoding="utf-8",
        xml_declaration=True,
        short_empty_elements=False,
    )


class Command(StrEnum):
    """Command options."""

    create_or_update_template = "create-or-update-template"
    build_theme_variants = "build-theme-variants"
    format_config_file = "format-config-file"
    get_distinct_style_names = "get-distinct-style-names"
    get_distinct_missing_style_names = "get-distinct-missing-style-names"


def create_arg_parser() -> ArgumentParser:
    """Create argument parser with various arguments.

    :return: argument parser
    :rtype: ArgumentParser
    """
    parser = ArgumentParser(
        description="Create or update Notepad++ style template XML file based on a "
        "configuration YAML file."
    )
    parser.add_argument(
        "command",
        type=Command,
        help="Command to execute.",
        choices=list(Command),
    )
    parser.add_argument(
        "--source",
        type=str,
        help="Path to the source stylers.xml file.",
        default="stylers.xml",
    )
    parser.add_argument(
        "--target",
        type=str,
        help="Path to the target template XML file to be created or updated.",
        default="template.xml",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to the configuration YAML file.",
        default="config.yaml",
    )
    return parser


def main():
    """Entry point."""
    parser = create_arg_parser()
    args = parser.parse_args()

    match args.command:
        case Command.create_or_update_template:
            create_or_update_template(
                source_file_path=args.source,
                target_file_path=args.target,
                config_file_path=args.config,
            )

        case Command.build_theme_variants:
            subprocess.run(  # noqa: S603
                [  # noqa: S607
                    "npx",
                    "@rose-pine/build",
                    "-t",
                    args.target,
                    "-o",
                    ".",
                    "-f",
                    "hex-ns",
                ],
                check=True,
            )

        case Command.format_config_file:
            styles = load_styles_from_config(args.config)
            format_config_file(
                config_file_path=args.config,
                styles=styles,
            )

        case Command.get_distinct_style_names:
            root = parse_xml_file(args.source)
            lexer_styles = get_lexer_styles(root)
            distinct_style_names = get_distinct_style_names(lexer_styles)
            print("Distinct style names:")
            for name in distinct_style_names:
                print(name)
            print(f"Distinct style count: {len(distinct_style_names)}")

        case Command.get_distinct_missing_style_names:
            styles = load_styles_from_config(args.config)
            root = parse_xml_file(args.source)
            lexer_styles = get_lexer_styles(root)
            missing_style_names = get_distinct_missing_style_names(
                lexer_styles,
                styles,
            )
            print("Missing style names:")
            for name in missing_style_names:
                print(name)
            print(f"Missing style count: {len(missing_style_names)}")


if __name__ == "__main__":
    main()
