import java.io.File;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;

/** Host JVM regression tests for Android font identity, without starting an Activity. */
public final class FontContentTest {
    public static void main(String[] args) throws Exception {
        Class<?> extras = Class.forName("com.artcraft.vectorcraft.VectorCraftExtras");
        Method digest = extras.getDeclaredMethod("fontDigest", File.class);
        Method contains = extras.getDeclaredMethod("containsFont", File.class, String.class);
        digest.setAccessible(true);
        contains.setAccessible(true);
        Path root = Files.createTempDirectory("vectorcraft-font-test-");
        try {
            Path imported = Files.createDirectories(root.resolve("Imported"));
            Path old = imported.resolve("font-legacy-uuid.ttf");
            Files.write(old, new byte[] {0, 1, 0, 0, 42, 13});
            String hash = (String) digest.invoke(null, old.toFile());
            if (!(Boolean) contains.invoke(null, root.toFile(), hash))
                throw new AssertionError("Legacy font was not recognized");
            Path same = root.resolve("renamed.otf");
            Files.copy(old, same);
            if (!hash.equals(digest.invoke(null, same.toFile())))
                throw new AssertionError("Filename changed content identity");
            Files.write(same, new byte[] {0, 1, 0, 0, 42, 14});
            if (hash.equals(digest.invoke(null, same.toFile())))
                throw new AssertionError("Different font contents conflated");
            if ((Boolean) contains.invoke(null, root.resolve("missing").toFile(), hash))
                throw new AssertionError("Missing directory reported a match");
            if (!Files.exists(old)) throw new AssertionError("Legacy file removed");
            System.out.println("PASS: legacy identity, filename independence, distinct content, missing directory, preservation");
        } finally {
            try (var paths = Files.walk(root)) {
                for (Path path : paths.sorted(java.util.Comparator.reverseOrder()).toList())
                    Files.delete(path);
            }
        }
    }
}
