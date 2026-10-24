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
                return 2;
            }

            string backendDir = Path.Combine(root, "backend");
            string python = LocatePython(root);
            if (python == null)
            {
                Fail(@"找不到 Python：请确认 backend\.venv\Scripts\python.exe 存在，或已安装 Python 3.12+。");
                return 3;
            }

            string baseUrl = "http://127.0.0.1:" + _port;
            string logDir = Path.Combine(root, "logs");
            Directory.CreateDirectory(logDir);
            string logPath = Path.Combine(logDir, "server-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + ".log");

            Console.WriteLine();
            Console.WriteLine("  活动报名与签到管理系统");
            Console.WriteLine("  ------------------------");

            if (IsHealthy(baseUrl))
            {
                Console.WriteLine("  服务已在运行：" + baseUrl);
                OpenBrowser(baseUrl + "/admin/");
                Console.WriteLine("  按任意键关闭本窗口（不会停止已在运行的服务）。");
                Console.ReadKey(true);
                return 0;
            }

            if (!File.Exists(Path.Combine(root, "web-app", "dist", "index.html")))
            {
                Console.WriteLine(@"  [提示] 未找到前端构建产物 web-app\dist，页面可能无法显示。");
                Console.WriteLine("         请在 admin-web、web-app 目录运行 npm.cmd run build 重新构建。");
            }

            if (!File.Exists(Path.Combine(backendDir, "event_system.db")))
            {
                Console.WriteLine("  首次启动，正在初始化数据库与演示账号...");
                if (RunCaptured(python, "-m alembic upgrade head", backendDir, logPath) != 0)
                {
                    Fail("数据库迁移失败，详见日志：" + logPath);
                    return 4;
                }
                RunCaptured(python, "scripts/create_admin.py --username admin --password admin12345 --name 系统管理员", backendDir, logPath);
            }

            Process server = StartServer(python, backendDir, logPath);
            Console.WriteLine("  正在启动服务（端口 " + _port + "）...");

            DateTime deadline = DateTime.UtcNow.AddSeconds(60);
            bool ready = false;
            while (DateTime.UtcNow < deadline)
            {
                if (server.HasExited)
                {
                    Fail("服务启动失败（退出码 " + server.ExitCode + "），详见日志：" + logPath);
                    Console.WriteLine("  按任意键退出。");
                    Console.ReadKey(true);
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
                Fail("服务在 60 秒内没有就绪，详见日志：" + logPath);
                TryKill(server);
                Console.WriteLine("  按任意键退出。");
                Console.ReadKey(true);
                return 6;
            }

            Console.WriteLine();
            Console.WriteLine("  参与者页面  " + baseUrl + "/");
            Console.WriteLine("  管理后台    " + baseUrl + "/admin/");
            Console.WriteLine("  默认账号    admin / admin12345（首次启动创建，请尽快修改）");
            Console.WriteLine("  运行日志    " + logPath);
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
                // 无交互控制台（后台运行）时保持服务，直到进程被结束。
                Thread.Sleep(Timeout.Infinite);
            }
            else
            {
                Console.ReadLine();
            }
            TryKill(server);
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

        private static Process StartServer(string python, string workingDir, string logPath)
        {
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = python;
            info.Arguments = "-m uvicorn app.main:app --host 127.0.0.1 --port " + _port;
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

        private static readonly object LogLock = new object();

        private static void AppendLog(string logPath, string line)
        {
            if (line == null) return;
            lock (LogLock)
            {
                try { File.AppendAllText(logPath, line + Environment.NewLine, Encoding.UTF8); }
                catch { }
            }
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
