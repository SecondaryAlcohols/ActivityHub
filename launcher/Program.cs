using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace EventSystemLauncher
{
    internal static class Program
    {
        private static int _port = 8000;
        private static bool _noBrowser;
        private static bool _participant;
        private static IntPtr _job = IntPtr.Zero;
        private static string _launcherLog;
        private static readonly object LogLock = new object();

        private static int Main(string[] args)
        {
            try { Console.OutputEncoding = Encoding.UTF8; }
            catch { }
            Console.Title = "活动报名与签到管理系统";

            ParseArgs(args);

            string root = FindRepoRoot();
            if (root == null)
            {
                Fail("找不到项目目录：请把本程序放在项目根目录（与 backend、admin-web 同级）后再运行。");
                Pause();
                return 2;
            }

            Directory.CreateDirectory(Path.Combine(root, "logs"));
            _launcherLog = Path.Combine(root, "logs", "launcher.log");
            Log("=== 启动 launcher ===");
            Log("exe=" + Process.GetCurrentProcess().MainModule.FileName);
            Log("root=" + root);

            string backendDir = Path.Combine(root, "backend");
            string python = LocatePython(root);
            if (python == null)
            {
                Fail(@"找不到 Python：请确认 backend\.venv\Scripts\python.exe 存在，或已安装 Python 3.12+。");
                Log("找不到 python");
                Pause();
                return 3;
            }
            Log("python=" + python);

            Console.WriteLine();
            Console.WriteLine("  活动报名与签到管理系统");
            Console.WriteLine("  ------------------------");

            bool alreadyRunning;
            bool skipped;
            int port = ResolvePort(_port, out alreadyRunning, out skipped);
            if (port <= 0)
            {
                Fail("需要用的端口都被占用了，请先关闭占用端口的程序再试。");
                Pause();
                return 7;
            }
            string baseUrl = "http://127.0.0.1:" + port;
            Log("port=" + port + " alreadyRunning=" + alreadyRunning);

            if (alreadyRunning)
            {
                Console.WriteLine("  服务已在运行：" + baseUrl);
                OpenBrowser(baseUrl + "/admin/");
                Console.WriteLine("  按任意键关闭本窗口（不会停止已在运行的服务）。");
                Pause();
                return 0;
            }

            if (skipped)
            {
                Console.WriteLine("  [提示] 端口 " + _port + " 上有一个旧服务，已改用 " + port + "。");
                Console.WriteLine("         如需使用 " + _port + "，请先关闭占用它的程序。");
            }

            if (!File.Exists(Path.Combine(root, "web-app", "dist", "index.html")))
            {
                Console.WriteLine(@"  [提示] 未找到前端构建产物 web-app\dist，页面可能无法显示。");
                Console.WriteLine("         请在 admin-web、web-app 目录运行 npm.cmd run build 重新构建。");
            }

            if (!File.Exists(Path.Combine(backendDir, "event_system.db")))
            {
                Console.WriteLine("  首次启动，正在初始化数据库与演示账号...");
                if (RunCaptured(python, "-m alembic upgrade head", backendDir, _launcherLog) != 0)
                {
                    Fail("数据库迁移失败，详见日志：" + _launcherLog);
                    Pause();
                    return 4;
                }
                RunCaptured(python, "scripts/create_admin.py --username admin --password admin12345 --name 系统管理员", backendDir, _launcherLog);
            }

            string serverLog = Path.Combine(root, "logs", "server-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + ".log");
            Process server = StartServer(python, port, backendDir, serverLog);
            Log("server pid=" + server.Id + " log=" + serverLog);
            Console.WriteLine("  正在启动服务（端口 " + port + "）...");

            DateTime deadline = DateTime.UtcNow.AddSeconds(60);
            bool ready = false;
            while (DateTime.UtcNow < deadline)
            {
                if (server.HasExited)
                {
                    Fail("服务启动失败（退出码 " + server.ExitCode + "），日志末尾：");
                    PrintTail(serverLog, 12);
                    Log("server exited early code=" + server.ExitCode);
                    Pause();
                    return 5;
                }
                if (IsHealthy(baseUrl))
                {
                    ready = true;
                    break;
                }
                Thread.Sleep(300);
            }

            if (!ready)
            {
                Fail("服务在 60 秒内没有就绪，日志末尾：");
                PrintTail(serverLog, 12);
                TryKill(server);
                Pause();
                return 6;
            }

            Log("ready on " + baseUrl);
            Console.WriteLine();
            Console.WriteLine("  参与者页面  " + baseUrl + "/");
            Console.WriteLine("  管理后台    " + baseUrl + "/admin/");
            Console.WriteLine("  默认账号    admin / admin12345（首次启动创建，请尽快修改）");
            Console.WriteLine("  运行日志    " + serverLog);
            Console.WriteLine();
            Console.WriteLine("  按 Enter 停止服务并退出；直接关闭窗口也会停止服务。");

            if (!_noBrowser)
            {
                OpenBrowser(_participant ? baseUrl + "/" : baseUrl + "/admin/");
            }

            Console.CancelKeyPress += delegate(object sender, ConsoleCancelEventArgs e)
            {
                e.Cancel = true;
                TryKill(server);
                Environment.Exit(0);
            };

            if (Console.IsInputRedirected)
            {
                Thread.Sleep(Timeout.Infinite);
            }
            else
            {
                Console.ReadLine();
            }
            TryKill(server);
            Log("=== 正常退出 ===");
            return 0;
        }

        private static void ParseArgs(string[] argv)
        {
            for (int i = 0; i < argv.Length; i++)
            {
                switch (argv[i])
                {
                    case "--port":
                        if (i + 1 < argv.Length)
                        {
                            int parsed;
                            if (int.TryParse(argv[i + 1], out parsed)) _port = parsed;
                            i++;
                        }
                        break;
                    case "--no-browser":
                        _noBrowser = true;
                        break;
                    case "--participant":
                        _participant = true;
                        break;
                }
            }
        }

        // 返回可用的端口；alreadyRunning 为 true 表示这个端口上已经是本项目（含前端）。
        private static int ResolvePort(int wanted, out bool alreadyRunning, out bool skipped)
        {
            alreadyRunning = false;
            skipped = false;
            string mode = Probe(wanted);
            Log("probe " + wanted + " => " + mode);

            if (mode == "ours")
            {
                alreadyRunning = true;
                return wanted;
            }

            if (mode == "foreign")
            {
                skipped = true;
                for (int p = wanted + 1; p <= wanted + 10; p++)
                {
                    string probe = Probe(p);
                    Log("probe " + p + " => " + probe);
                    if (probe == "ours")
                    {
                        alreadyRunning = true;
                        return p;
                    }
                    if (probe == "free") return p;
                }
                return -1;
            }

            return wanted;
        }

        // free：没有服务；ours：本项目（/admin/ 返回页面）；foreign：占用但不是本项目。
        private static string Probe(int port)
        {
            string baseUrl = "http://127.0.0.1:" + port;
            if (!IsHealthy(baseUrl)) return "free";
            try
            {
                WebRequest request = WebRequest.Create(baseUrl + "/admin/");
                request.Timeout = 2500;
                using (WebResponse response = request.GetResponse())
                using (StreamReader reader = new StreamReader(response.GetResponseStream(), Encoding.UTF8))
                {
                    string html = reader.ReadToEnd();
                    if (html.IndexOf("<!doctype", StringComparison.OrdinalIgnoreCase) >= 0
                        || html.IndexOf("<html", StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        return "ours";
                    }
                }
            }
            catch { }
            return "foreign";
        }

        private static string FindRepoRoot()
        {
            string[] starts = new string[] { AppDomain.CurrentDomain.BaseDirectory, Directory.GetCurrentDirectory() };
            foreach (string start in starts)
            {
                DirectoryInfo dir = new DirectoryInfo(start);
                for (int i = 0; i < 6 && dir != null; i++, dir = dir.Parent)
                {
                    bool hasBackend = File.Exists(Path.Combine(dir.FullName, "backend", "app", "main.py"));
                    bool hasAdmin = Directory.Exists(Path.Combine(dir.FullName, "admin-web"));
                    if (hasBackend && hasAdmin) return dir.FullName;
                }
            }
            return null;
        }

        private static string LocatePython(string root)
        {
            string venv = Path.Combine(root, "backend", ".venv", "Scripts", "python.exe");
            if (File.Exists(venv)) return venv;

            string path = Environment.GetEnvironmentVariable("PATH");
            if (path != null)
            {
                foreach (string entry in path.Split(Path.PathSeparator))
                {
                    if (entry.Trim().Length == 0) continue;
                    string candidate = Path.Combine(entry.Trim(), "python.exe");
                    if (File.Exists(candidate)) return candidate;
                }
            }
            return null;
        }

        private static bool IsHealthy(string baseUrl)
        {
            try
            {
                WebRequest request = WebRequest.Create(baseUrl + "/api/health");
                request.Timeout = 1200;
                using (WebResponse response = request.GetResponse())
                {
                    return true;
                }
            }
            catch
            {
                return false;
            }
        }

        private static Process StartServer(string python, int port, string workingDir, string logPath)
        {
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = python;
            info.Arguments = "-m uvicorn app.main:app --host 127.0.0.1 --port " + port;
            info.WorkingDirectory = workingDir;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;

            Process process = new Process();
            process.StartInfo = info;
            process.EnableRaisingEvents = true;
            process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e) { AppendLog(logPath, e.Data); };
            process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e) { AppendLog(logPath, e.Data); };
            process.Start();
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
            AttachToJob(process);
            return process;
        }

        private static void AppendLog(string logPath, string line)
        {
            if (line == null) return;
            lock (LogLock)
            {
                try { File.AppendAllText(logPath, line + Environment.NewLine, Encoding.UTF8); }
                catch { }
            }
        }

        private static void Log(string message)
        {
            if (_launcherLog == null) return;
            lock (LogLock)
            {
                try
                {
                    File.AppendAllText(_launcherLog,
                        DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + message + Environment.NewLine,
                        Encoding.UTF8);
                }
                catch { }
            }
        }

        private static void PrintTail(string path, int lines)
        {
            try
            {
                if (!File.Exists(path)) { Console.WriteLine("  （暂无日志）"); return; }
                string[] all = File.ReadAllLines(path);
                int start = Math.Max(0, all.Length - lines);
                for (int i = start; i < all.Length; i++) Console.WriteLine("  " + all[i]);
            }
            catch { }
        }

        private static int RunCaptured(string fileName, string arguments, string workingDir, string logPath)
        {
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = fileName;
            info.Arguments = arguments;
            info.WorkingDirectory = workingDir;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;

            using (Process process = Process.Start(info))
            {
                string output = process.StandardOutput.ReadToEnd() + process.StandardError.ReadToEnd();
                process.WaitForExit();
                AppendLog(logPath, output);
                return process.ExitCode;
            }
        }

        private static void TryKill(Process process)
        {
            try
            {
                if (!process.HasExited)
                {
                    Process.Start(new ProcessStartInfo("taskkill", "/PID " + process.Id + " /T /F")
                    {
                        CreateNoWindow = true,
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true
                    });
                    process.WaitForExit(5000);
                }
            }
            catch { }
        }

        private static void OpenBrowser(string url)
        {
            try
            {
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            }
            catch
            {
                Console.WriteLine("  无法自动打开浏览器，请手动访问：" + url);
            }
        }

        private static void Pause()
        {
            if (Console.IsInputRedirected) return;
            Console.WriteLine();
            Console.WriteLine("  按任意键关闭窗口。");
            try { Console.ReadKey(true); } catch { }
        }

        private static void Fail(string message)
        {
            Console.WriteLine();
            Console.WriteLine("  [错误] " + message);
        }

        // 让 uvicorn 子进程跟随本程序退出，避免关掉窗口后端口仍被占用。
        private const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000;
        private const int JobObjectExtendedLimitInformation = 9;

        [StructLayout(LayoutKind.Sequential)]
        private struct JOBOBJECT_BASIC_LIMIT_INFORMATION
        {
            public long PerProcessUserTimeLimit;
            public long PerJobUserTimeLimit;
            public uint LimitFlags;
            public UIntPtr MinimumWorkingSetSize;
            public UIntPtr MaximumWorkingSetSize;
            public uint ActiveProcessLimit;
            public UIntPtr Affinity;
            public uint PriorityClass;
            public uint SchedulingClass;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct IO_COUNTERS
        {
            public ulong ReadOperationCount;
            public ulong WriteOperationCount;
            public ulong OtherOperationCount;
            public ulong ReadTransferCount;
            public ulong WriteTransferCount;
            public ulong OtherTransferCount;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        {
            public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
            public IO_COUNTERS IoInfo;
            public UIntPtr ProcessMemoryLimit;
            public UIntPtr JobMemoryLimit;
            public UIntPtr PeakProcessMemoryUsed;
            public UIntPtr PeakJobMemoryUsed;
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
        private static extern IntPtr CreateJobObject(IntPtr attributes, string name);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref JOBOBJECT_EXTENDED_LIMIT_INFORMATION info, int length);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

        private static void AttachToJob(Process process)
        {
            try
            {
                if (_job == IntPtr.Zero) _job = CreateJobObject(IntPtr.Zero, null);
                if (_job == IntPtr.Zero) return;

                JOBOBJECT_EXTENDED_LIMIT_INFORMATION info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
                info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
                SetInformationJobObject(_job, JobObjectExtendedLimitInformation, ref info, Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION)));
                AssignProcessToJobObject(_job, process.Handle);
            }
            catch { }
        }
    }
}
