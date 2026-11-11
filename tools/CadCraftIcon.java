import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.geom.Path2D;
import java.awt.geom.RoundRectangle2D;
import java.awt.image.BufferedImage;
import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.imageio.ImageIO;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

/** Converts the reviewed CADCraft Cc logo SVG to PNG using only the JDK. */
public class CadCraftIcon {
    private static Path2D.Double path(String data) {
        Matcher matcher = Pattern.compile("[MLZmlz]|-?(?:[0-9]+(?:\\.[0-9]+)?|\\.[0-9]+)").matcher(data);
        List<String> tokens = new ArrayList<>();
        while (matcher.find()) tokens.add(matcher.group());
        Path2D.Double result = new Path2D.Double(Path2D.WIND_NON_ZERO);
        char command = ' ';
        int index = 0;
        while (index < tokens.size()) {
            String token = tokens.get(index);
            if (token.length() == 1 && Character.isLetter(token.charAt(0))) {
                command = Character.toUpperCase(token.charAt(0));
                index++;
                if (command == 'Z') { result.closePath(); command = ' '; }
                continue;
            }
            if (command != 'M' && command != 'L') throw new IllegalArgumentException("Unexpected SVG path command");
            if (index + 1 >= tokens.size()) throw new IllegalArgumentException("Unpaired SVG coordinate");
            double x = Double.parseDouble(tokens.get(index++));
            double y = Double.parseDouble(tokens.get(index++));
            if (command == 'M') { result.moveTo(x, y); command = 'L'; }
            else result.lineTo(x, y);
        }
        return result;
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("Usage: CadCraftIcon.java Cc-launcher-icon.svg output.png");
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        Element svg = factory.newDocumentBuilder().parse(new File(args[0])).getDocumentElement();
        NodeList rects = svg.getElementsByTagName("rect");
        NodeList paths = svg.getElementsByTagName("path");
        if (rects.getLength() != 1 || paths.getLength() != 1) throw new IllegalArgumentException("Unexpected CADCraft icon SVG structure");
        Element rect = (Element) rects.item(0);
        Element glyph = (Element) paths.item(0);
        if (!glyph.getAttribute("d").matches("[MLZmlz0-9.,\\s-]+")) throw new IllegalArgumentException("Only reviewed straight-line Cc SVG is supported");
        BufferedImage image = new BufferedImage(1024, 1024, BufferedImage.TYPE_INT_ARGB);
        Graphics2D g = image.createGraphics();
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.scale(0.5, 0.5);
        double x = Double.parseDouble(rect.getAttribute("x"));
        double y = Double.parseDouble(rect.getAttribute("y"));
        double w = Double.parseDouble(rect.getAttribute("width"));
        double h = Double.parseDouble(rect.getAttribute("height"));
        double r = Double.parseDouble(rect.getAttribute("rx"));
        RoundRectangle2D.Double base = new RoundRectangle2D.Double(x, y, w, h, r*2, r*2);
        g.setColor(Color.decode(rect.getAttribute("fill")));
        g.fill(base);
        g.setColor(Color.decode(rect.getAttribute("stroke")));
        g.setStroke(new BasicStroke(Float.parseFloat(rect.getAttribute("stroke-width"))));
        g.draw(base);
        g.setColor(Color.decode(glyph.getAttribute("fill")));
        g.fill(path(glyph.getAttribute("d")));
        g.dispose();
        if (!ImageIO.write(image, "png", new File(args[1]))) throw new IllegalStateException("Could not write PNG");
        System.out.println("Rendered reviewed Cc SVG using JDK graphics: " + args[1]);
    }
}
