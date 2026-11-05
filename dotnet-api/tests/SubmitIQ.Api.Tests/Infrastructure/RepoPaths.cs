namespace SubmitIQ.Api.Tests.Infrastructure;

/// <summary>Finds files in the SubmitIQ repository (the tests read the Python side's data in place).</summary>
public static class RepoPaths
{
    public static string Root { get; } = FindRoot();

    public static string AppetiteYaml => Path.Combine(Root, "rules", "appetite.yaml");
    public static string Contracts => Path.Combine(Root, "dotnet-api", "contracts");
    public static string Submissions => Path.Combine(Root, "data", "submissions");

    private static string FindRoot()
    {
        for (var dir = new DirectoryInfo(AppContext.BaseDirectory); dir is not null; dir = dir.Parent)
        {
            if (File.Exists(Path.Combine(dir.FullName, "rules", "appetite.yaml")) && Directory.Exists(Path.Combine(dir.FullName, "dotnet-api")))
                return dir.FullName;
        }
        throw new DirectoryNotFoundException("could not find the SubmitIQ repository root above " + AppContext.BaseDirectory);
    }
}
